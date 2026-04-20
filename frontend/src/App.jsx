import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;
const WS_BASE = import.meta.env.VITE_WS_BASE;

const emptySummary = {
  total_ingested_messages: 0,
  total_messages: 0,
  messages_last_minute: 0,
  unique_users_last_minute: 0,
  top_topics: [],
  topic_groups: [],
  spam_clusters: [],
  recent_messages: [],
};

export default function App() {
  const [summary, setSummary] = useState(emptySummary);
  const [form, setForm] = useState({ username: "demo_user", body: "" });
  const [loading, setLoading] = useState(false);

  async function refreshSummary() {
    const response = await fetch(`${API_BASE}/api/summary`);
    const data = await response.json();
    setSummary(data);
  }

  useEffect(() => {
    refreshSummary();
    const ws = new WebSocket(`${WS_BASE}/ws`);
    const refreshIntervalId = window.setInterval(refreshSummary, 5000);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setSummary(data);
    };

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
    };

    return () => {
      window.clearInterval(refreshIntervalId);
      ws.close();
    };
  }, []);

  async function submitMessage(event) {
    event.preventDefault();
    if (!form.body.trim()) {
      return;
    }

    setLoading(true);
    await fetch(`${API_BASE}/api/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setForm((current) => ({ ...current, body: "" }));
    await refreshSummary();
    setLoading(false);
  }

  async function simulateMessages() {
    setLoading(true);
    await fetch(`${API_BASE}/api/simulate?count=15`, { method: "POST" });
    await refreshSummary();
    setLoading(false);
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Moderator Dashboard</p>
          <h1>Chat Analyser</h1>
          <p className="hero-copy">
            Watch live chat topics converge, spot repeated spam, and keep the
            human moderator in the loop.
          </p>
        </div>
        <button className="secondary-button" onClick={simulateMessages}>
          Load Sample Chat
        </button>
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Total Ingested"
          value={summary.total_ingested_messages}
        />
        <MetricCard label="Messages In Memory" value={summary.total_messages} />
        <MetricCard
          label="Messages / Minute"
          value={summary.messages_last_minute}
        />
        <MetricCard
          label="Active Users / Minute"
          value={summary.unique_users_last_minute}
        />
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-header">
            <h2>Top Topics</h2>
            <span>Rolling signal</span>
          </div>
          <div className="tag-list">
            {summary.top_topics.length === 0 ? (
              <p className="empty-state">No topic data yet.</p>
            ) : (
              summary.top_topics.map((topic) => (
                <div className="topic-pill" key={topic.topic}>
                  <span>{topic.topic}</span>
                  <strong>{topic.count}</strong>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Topic Groups</h2>
            <span>Shared subject phrases</span>
          </div>
          <div className="cluster-list">
            {summary.topic_groups.length === 0 ? (
              <p className="empty-state">No repeated topic groups yet.</p>
            ) : (
              summary.topic_groups.map((group) => (
                <div className="cluster-card" key={group.phrase}>
                  <p>{group.phrase}</p>
                  <small>
                    {group.count} messages across {group.users.length} users
                  </small>
                  <small>{group.sample_messages.join(" | ")}</small>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-header">
            <h2>Spam Clusters</h2>
            <span>Near-duplicate messages</span>
          </div>
          <div className="cluster-list">
            {summary.spam_clusters.length === 0 ? (
              <p className="empty-state">No suspicious repetition yet.</p>
            ) : (
              summary.spam_clusters.map((cluster) => (
                <div className="cluster-card" key={cluster.text}>
                  <div className="cluster-card-header">
                    <p>{cluster.text}</p>
                    <span className={`severity-badge severity-${cluster.severity}`}>
                      {cluster.severity}
                    </span>
                  </div>
                  <small>
                    {cluster.count} messages across {cluster.users.length} users
                  </small>
                  <small>
                    {cluster.recent_count} in the last 30s across{" "}
                    {cluster.recent_unique_users} users
                  </small>
                  <small>{cluster.severity_reason}</small>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Recent Messages</h2>
            <span>Cluster assignment</span>
          </div>
          <div className="message-list">
            {summary.recent_messages.length === 0 ? (
              <p className="empty-state">Submit a message to begin.</p>
            ) : (
              summary.recent_messages.map((message, index) => (
                <div className="message-row" key={`${message.timestamp}-${index}`}>
                  <div>
                    <strong>{message.username}</strong>
                    <p>{message.original_body}</p>
                  </div>
                  <div className="message-output">
                    <code>{message.cluster_label}</code>
                    <small>cluster: {message.cluster_key}</small>
                    <small>normalised: {message.normalised_body}</small>
                  </div>
                </div>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-header">
            <h2>Send Test Message</h2>
            <span>Manual ingestion</span>
          </div>
          <form className="composer" onSubmit={submitMessage}>
            <label>
              Username
              <input
                value={form.username}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    username: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              Message
              <textarea
                rows="6"
                placeholder="Type something noisy like: thsi game sux!!!"
                value={form.body}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    body: event.target.value,
                  }))
                }
              />
            </label>
            <button className="primary-button" disabled={loading} type="submit">
              {loading ? "Working..." : "Submit Message"}
            </button>
          </form>
        </article>
      </section>
    </main>
  );
}

function MetricCard({ label, value }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
