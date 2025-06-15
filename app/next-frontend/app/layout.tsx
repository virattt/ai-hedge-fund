// app/next-frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../src/styles/globals.css"; // Adjusted path
import MainLayout from "@/components/layout/main-layout"; // Import MainLayout

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Financial Analysis Platform", // Updated title
  description: "A platform for financial analysis and portfolio management.", // Updated description
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <MainLayout>{children}</MainLayout>
      </body>
    </html>
  );
}
