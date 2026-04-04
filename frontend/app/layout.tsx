import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { LearnerProfileProvider } from "@/components/providers/LearnerProfileProvider";
import { ConfirmDialogProvider } from "@/contexts/ConfirmDialogContext";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { AppInitializer } from "@/components/providers/AppInitializer";
import { RootErrorBoundary } from "@/components/providers/RootErrorBoundary";
import { Toaster } from "sonner";
import "./globals.css";
import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";
import { cn } from "@/lib/utils";

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
      <body className={cn("min-h-screen bg-gray-50 dark:bg-gray-900 antialiased")}>
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
          <Toaster richColors position="bottom-right" visibleToasts={5} />
        </ThemeProvider>
      </body>
    </html>
  );
}
