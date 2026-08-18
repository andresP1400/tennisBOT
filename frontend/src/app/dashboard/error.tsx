"use client";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      style={{
        fontFamily: "system-ui, sans-serif",
        color: "#e0e0e0",
        padding: "2rem",
      }}
    >
      <h1 style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>
        Dashboard error
      </h1>
      <p style={{ color: "#a0a0a0", marginBottom: "1.5rem" }}>
        {error.message || "Unexpected error in the dashboard."}
      </p>
      <button
        type="button"
        onClick={reset}
        style={{
          padding: "0.5rem 1rem",
          background: "#00d4ff",
          color: "#000",
          border: "none",
          borderRadius: 4,
          cursor: "pointer",
        }}
      >
        Try again
      </button>
    </div>
  );
}
