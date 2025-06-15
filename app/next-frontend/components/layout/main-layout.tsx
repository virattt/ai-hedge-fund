// app/next-frontend/components/layout/main-layout.tsx
import React from 'react';
import Link from 'next/link';
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex flex-col min-h-screen">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="mr-4 hidden md:flex">
            <Link href="/" className="mr-6 flex items-center space-x-2">
              <span className="hidden font-bold sm:inline-block">
                Financial Analysis Platform
              </span>
            </Link>
            <nav className="flex items-center space-x-6 text-sm font-medium">
              <Link href="/dashboard" className="transition-colors hover:text-foreground/80 text-foreground/60">Dashboard</Link>
              <Link href="/agents" className="transition-colors hover:text-foreground/80 text-foreground/60">Agents</Link>
              <Link href="/analysis" className="transition-colors hover:text-foreground/80 text-foreground/60">Analysis</Link>
              <Link href="/portfolio" className="transition-colors hover:text-foreground/80 text-foreground/60">Portfolio</Link>
              <Link href="/setup-guide" className="transition-colors hover:text-foreground/80 text-foreground/60">Setup</Link>
            </nav>
          </div>
          <div className="flex flex-1 items-center justify-between space-x-2 md:hidden">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Toggle Menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="pr-0">
                <Link href="/" className="mr-6 flex items-center space-x-2">
                  <span className="font-bold">Financial Platform</span>
                </Link>
                <div className="flex flex-col space-y-3 pt-6">
                  <Link href="/dashboard">Dashboard</Link>
                  <Link href="/agents">Agents</Link>
                  <Link href="/analysis">Analysis</Link>
                  <Link href="/portfolio">Portfolio</Link>
                  <Link href="/setup-guide">Setup Guide</Link>
                </div>
              </SheetContent>
            </Sheet>
            <Link href="/" className="flex items-center space-x-2">
              <span className="font-bold">Financial Platform</span>
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1 container py-6">{children}</main>
      <footer className="py-6 md:px-8 md:py-0 border-t">
        <div className="container flex flex-col items-center justify-between gap-4 md:h-24 md:flex-row">
          <p className="text-center text-sm leading-loose text-muted-foreground md:text-left">
            Built with Next.js and ShadCN.
          </p>
        </div>
      </footer>
    </div>
  );
}
