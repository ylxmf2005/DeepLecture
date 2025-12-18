import { parseTimestampToSeconds, TIMESTAMP_REGEX } from "@/lib/markdown/timestamps";

type MdastNode = {
    type: string;
    value?: string;
    url?: string;
    children?: MdastNode[];
    [key: string]: unknown;
};

const SKIP_NODE_TYPES = new Set(["link", "linkReference", "code", "inlineCode"]);

function splitTextIntoNodes(text: string): MdastNode[] {
    // Reset lastIndex for global regex reuse
    TIMESTAMP_REGEX.lastIndex = 0;
    const matches = Array.from(text.matchAll(TIMESTAMP_REGEX));
    if (matches.length === 0) return [{ type: "text", value: text }];

    const nodes: MdastNode[] = [];
    let cursor = 0;

    for (const match of matches) {
        const fullMatch = match[0]; // e.g., "[5:30]"
        const timeContent = match[1]; // e.g., "5:30" (captured group)
        const matchIndex = match.index ?? -1;
        if (matchIndex < cursor) continue;

        const seconds = parseTimestampToSeconds(timeContent);
        if (seconds === null) continue;

        if (matchIndex > cursor) {
            nodes.push({ type: "text", value: text.slice(cursor, matchIndex) });
        }

        // Keep the brackets in display text for visual clarity
        nodes.push({
            type: "link",
            url: `#t=${seconds}`,
            children: [{ type: "text", value: fullMatch }],
        });

        cursor = matchIndex + fullMatch.length;
    }

    if (cursor < text.length) {
        nodes.push({ type: "text", value: text.slice(cursor) });
    }

    const hasLink = nodes.some((n) => n.type === "link");
    return hasLink ? nodes : [{ type: "text", value: text }];
}

function transformTree(node: MdastNode): void {
    if (SKIP_NODE_TYPES.has(node.type)) return;

    if (!Array.isArray(node.children) || node.children.length === 0) return;

    const nextChildren: MdastNode[] = [];

    for (const child of node.children) {
        if (SKIP_NODE_TYPES.has(child.type)) {
            nextChildren.push(child);
            continue;
        }

        if (child.type === "text" && typeof child.value === "string") {
            nextChildren.push(...splitTextIntoNodes(child.value));
            continue;
        }

        transformTree(child);
        nextChildren.push(child);
    }

    node.children = nextChildren;
}

export function remarkSeekableTimestamps() {
    return (tree: MdastNode) => {
        transformTree(tree);
    };
}
