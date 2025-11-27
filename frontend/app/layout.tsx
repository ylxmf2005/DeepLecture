import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Header } from "@/components/Header";
import { LearnerProfileProvider } from "@/components/LearnerProfileProvider";
import { ConfirmDialogProvider } from "@/contexts/ConfirmDialogContext";
import { ThemeProvider } from "@/components/ThemeProvider";
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
          <ConfirmDialogProvider>
            <LearnerProfileProvider>
              <Header />
              <main className="container mx-auto py-8 px-4">
                {children}
              </main>
            </LearnerProfileProvider>
          </ConfirmDialogProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
