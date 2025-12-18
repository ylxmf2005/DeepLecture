export interface FactVerificationReport {
    reportId: string;
    contentId: string;
    language: string;
    createdAt: string;
    claims: Claim[];
    summary: string;
}

export interface Claim {
    claimId: string;
    text: string;
    start: number;
    end: number;
    verdict: "supported" | "disputed" | "unverifiable" | "context_missing";
    confidence: number;
    evidence: Evidence[];
    notes: string;
}

export interface Evidence {
    url: string;
    title: string;
    publisher: string;
    quote: string;
    retrievedAt: string;
}
