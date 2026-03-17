import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "./components/Sidebar";
import SidebarLayout from "./components/SidebarLayout";
import { NavHoverProvider } from "./components/NavHoverContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Jeromelu | AI SuperCoach Analyst",
  description: "AI-powered NRL SuperCoach analyst. Watching everything. Reading everyone. Making moves.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <NavHoverProvider>
          <Sidebar />
          <SidebarLayout>{children}</SidebarLayout>
        </NavHoverProvider>
      </body>
    </html>
  );
}
