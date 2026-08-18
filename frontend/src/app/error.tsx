"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          background: "#0a0a0a",
          color: "#e0e0e0",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
        }}
      >
        <div style={{ maxWidth: 480, textAlign: "center" }}>
          <h1 style={{ fontSize: "1.75rem", marginBottom: "1rem" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#a0a0a0", marginBottom: "1.5rem" }}>
            {error.message || "Unexpected client error."}
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
      </body>
    </html>
  );
}
