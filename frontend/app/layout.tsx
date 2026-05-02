import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Plum — AI Claims Processing",
  description: "Employee benefits your team deserves. AI-powered claims processing by Plum.",
};

function PlumLogo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="16" cy="16" r="16" fill="#570e40"/>
        <path d="M10 22 C10 22 10 10 16 10 C22 10 22 16 16 16 C10 16 10 22 10 22Z" fill="#ff4052"/>
        <circle cx="16" cy="22" r="3.5" fill="#ff6a75"/>
      </svg>
      <span style={{ fontWeight: 700, fontSize: "1.25rem", color: "#570e40", letterSpacing: "-0.02em" }}>
        plum
      </span>
    </div>
  );
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col" style={{ background: "var(--plum-cream)" }}>
        {/* Nav */}
        <header style={{ background: "#fff", borderBottom: "1px solid #f0e8e0" }} className="sticky top-0 z-50">
          <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
            <PlumLogo />
            <span style={{ fontSize: "0.75rem", color: "#a0a5ab" }}>
              Employee Benefits &amp; Insurance
            </span>
          </div>
        </header>

        <div className="flex-1">{children}</div>

        {/* Footer */}
        <footer style={{ background: "#570e40", color: "#fff" }} className="mt-auto">
          <div className="max-w-4xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <svg width="20" height="20" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="16" fill="#460932"/>
                <path d="M10 22 C10 22 10 10 16 10 C22 10 22 16 16 16 C10 16 10 22 10 22Z" fill="#ff4052"/>
                <circle cx="16" cy="22" r="3.5" fill="#ff6a75"/>
              </svg>
              <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>plum</span>
              <span style={{ color: "#ff6a75", fontSize: "0.875rem" }}>— Care is our universal language</span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "#e8c4d8", textAlign: "center" }}>
              Project assignment by{" "}
              <span style={{ color: "#ffbf21", fontWeight: 600 }}>Kartik Kumar</span>
              {" "}· AI-powered claims processing demo
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
