import Link from "next/link";
import { Video, BookMarked } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

export function Header() {
    return (
        <header className="sticky top-0 z-50 w-full border-b border-border/5 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
            <div className="container mx-auto flex h-16 items-center justify-between px-4">
                <Link href="/" className="flex items-center gap-2.5 group">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
                        <Video className="h-5 w-5" />
                    </div>
                    <span className="text-lg font-bold tracking-tight bg-gradient-to-br from-foreground to-muted-foreground bg-clip-text text-transparent">
                        DeepLecture
                    </span>
                </Link>
                <nav className="flex items-center gap-6">
                    <Link
                        href="/"
                        className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                    >
                        Dashboard
                    </Link>
                    <Link
                        href="/vocabulary"
                        className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground flex items-center gap-1.5"
                    >
                        <BookMarked className="w-4 h-4" />
                        Vocabulary
                    </Link>
                    <a
                        href="https://github.com/your-repo/CourseSubtitle"
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                    >
                        GitHub
                    </a>
                    <div id="header-actions" className="flex items-center gap-2 pl-2">
                        <ThemeToggle />
                    </div>
                </nav>
            </div>
        </header>
    );
}
