import Image from "next/image";
import Link from "next/link";

export const metadata = {
  title: "HALO — AI Hair & Color Analysis",
  description:
    "Upload a photo and get your best cuts, color season, and AI previews in under a minute.",
};

const features = [
  {
    icon: "✂️",
    title: "Best Hairstyles for Your Face",
    body: "AI picks the cuts and lengths that flatter your face shape and hair type — with visual previews on your photo.",
  },
  {
    icon: "🎨",
    title: "Your Color Season",
    body: "Discover your season (Spring, Summer, Autumn, Winter) and the exact palette that makes your complexion glow.",
  },
  {
    icon: "⚡",
    title: "Ready in Under a Minute",
    body: "Drop a photo, get a full report with AI-generated style images — cuts, colors, what to avoid, and a bottom-line summary.",
  },
];

export default function Home() {
  return (
    <main
      style={{
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
        background: "#faf6f1",
        color: "#2c2622",
        minHeight: "100vh",
        margin: 0,
        padding: 0,
      }}
    >
      {/* NAV */}
      <nav
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "18px 32px",
          maxWidth: 1100,
          margin: "0 auto",
        }}
      >
        <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: "0.5px" }}>
          HALO<span style={{ color: "#6b8e5a" }}>.</span>
        </span>
        <Link
          href="/halo.html"
          style={{
            background: "#6b8e5a",
            color: "#fff",
            padding: "9px 20px",
            borderRadius: 10,
            fontWeight: 600,
            fontSize: 14,
            textDecoration: "none",
          }}
        >
          Try it free →
        </Link>
      </nav>

      {/* HERO */}
      <section
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding: "32px 24px 64px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 48,
          alignItems: "center",
        }}
      >
        <div>
          <p
            style={{
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: "2px",
              color: "#6b8e5a",
              marginBottom: 14,
              textTransform: "uppercase",
            }}
          >
            AI Hair &amp; Color Analysis
          </p>
          <h1
            style={{
              fontSize: "clamp(32px, 5vw, 52px)",
              fontWeight: 800,
              lineHeight: 1.1,
              margin: "0 0 20px",
              letterSpacing: "-0.5px",
            }}
          >
            Your best hair,
            <br />
            <span style={{ color: "#6b8e5a" }}>finally figured out.</span>
          </h1>
          <p
            style={{
              fontSize: 17,
              color: "#7a6f68",
              lineHeight: 1.6,
              margin: "0 0 32px",
              maxWidth: 440,
            }}
          >
            Drop a photo. In about a minute, see your best cuts, your color
            season, and AI previews of each style — on your actual face.
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <Link
              href="/halo.html"
              style={{
                background: "#6b8e5a",
                color: "#fff",
                padding: "14px 28px",
                borderRadius: 12,
                fontWeight: 700,
                fontSize: 16,
                textDecoration: "none",
                display: "inline-block",
              }}
            >
              Start my analysis →
            </Link>
            <span style={{ color: "#7a6f68", fontSize: 13 }}>
              Free · No sign-up required
            </span>
          </div>
        </div>

        <div
          style={{
            borderRadius: 20,
            overflow: "hidden",
            boxShadow: "0 20px 60px rgba(60,40,20,0.14)",
            background: "#e8dfd2",
          }}
        >
          <Image
            src="/screenshot.jpeg"
            alt="HALO hair analysis result showing style recommendations and color palette"
            width={620}
            height={480}
            style={{ width: "100%", height: "auto", display: "block" }}
            priority
          />
        </div>
      </section>

      {/* FEATURES */}
      <section
        style={{
          background: "#fff",
          padding: "64px 24px",
          borderTop: "1px solid #e8e1d8",
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <h2
            style={{
              textAlign: "center",
              fontSize: 28,
              fontWeight: 700,
              marginBottom: 48,
              letterSpacing: "-0.3px",
            }}
          >
            What you get
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 28,
            }}
          >
            {features.map((f) => (
              <div
                key={f.title}
                style={{
                  background: "#faf6f1",
                  border: "1px solid #e8e1d8",
                  borderRadius: 16,
                  padding: "28px 24px",
                }}
              >
                <div style={{ fontSize: 32, marginBottom: 14 }}>{f.icon}</div>
                <h3 style={{ fontWeight: 700, fontSize: 17, margin: "0 0 10px" }}>
                  {f.title}
                </h3>
                <p style={{ color: "#7a6f68", fontSize: 14, lineHeight: 1.6, margin: 0 }}>
                  {f.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA STRIP */}
      <section
        style={{
          background: "#6b8e5a",
          padding: "56px 24px",
          textAlign: "center",
        }}
      >
        <h2 style={{ color: "#fff", fontSize: 28, fontWeight: 700, margin: "0 0 12px" }}>
          Ready to see your best look?
        </h2>
        <p style={{ color: "rgba(255,255,255,0.8)", fontSize: 15, margin: "0 0 28px" }}>
          Free analysis · Takes about 60 seconds · No account needed
        </p>
        <Link
          href="/halo.html"
          style={{
            background: "#fff",
            color: "#6b8e5a",
            padding: "14px 32px",
            borderRadius: 12,
            fontWeight: 700,
            fontSize: 16,
            textDecoration: "none",
            display: "inline-block",
          }}
        >
          Upload a photo →
        </Link>
      </section>

      {/* FOOTER */}
      <footer
        style={{
          padding: "24px 32px",
          textAlign: "center",
          fontSize: 12,
          color: "#7a6f68",
          borderTop: "1px solid #e8e1d8",
        }}
      >
        HALO · AI-generated style guidance — a starting point, not a salon diagnosis.
      </footer>

      <style>{`
        @media (max-width: 720px) {
          section { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </main>
  );
}
