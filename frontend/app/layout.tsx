import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Header } from "@/components/layout/Header";
import { LearnerProfileProvider } from "@/components/providers/LearnerProfileProvider";
import { ConfirmDialogProvider } from "@/contexts/ConfirmDialogContext";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { AppInitializer } from "@/components/providers/AppInitializer";
import { RootErrorBoundary } from "@/components/providers/RootErrorBoundary";
import { Toaster } from "sonner";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CourseSubtitle",
  description: "Video subtitle generation and translation tool",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={cn(inter.className, "min-h-screen bg-gray-50 dark:bg-gray-900 antialiased")}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <RootErrorBoundary>
            <AppInitializer>
              <ConfirmDialogProvider>
                <LearnerProfileProvider>
                  <Header />
                  <main className="container mx-auto py-8 px-4">
                    {children}
                  </main>
                </LearnerProfileProvider>
              </ConfirmDialogProvider>
            </AppInitializer>
          </RootErrorBoundary>
          <Toaster richColors position="bottom-right" />
        </ThemeProvider>
      </body>
    </html>
  );
}
