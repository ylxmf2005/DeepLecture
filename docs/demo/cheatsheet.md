# Cheatsheet API

Generate high-density reference sheets for exam preparation and quick review.

## Use Cases

- **Open-book exams**: Quick lookup of formulas and definitions
- **Pre-exam review**: Fast scan of key concepts
- **Study reference**: Condensed knowledge for revision

## API Endpoints

### GET /api/cheatsheet

Retrieve existing cheatsheet for a content item.

**Query Parameters:**
- `content_id` (required): Content identifier

**Response:**
```json
{
  "content_id": "abc123",
  "content": "## Formulas\n\n| Formula | Description |\n|---------|-------------|\n| $E=mc^2$ | Energy-mass equivalence |",
  "updated_at": "2025-01-27T10:30:00Z"
}
```

### POST /api/cheatsheet

Save cheatsheet content (manual edit).

**Request Body:**
```json
{
  "content_id": "abc123",
  "content": "## My Cheatsheet\n\n..."
}
```

### POST /api/cheatsheet/generate

Generate a new cheatsheet from video content.

**Request Body:**
```json
{
  "content_id": "abc123",
  "language": "en",
  "context_mode": "auto",
  "min_criticality": "medium",
  "target_pages": 2,
  "subject_type": "stem"
}
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| content_id | string | required | Content identifier |
| language | string | required | Output language (e.g., "en", "zh") |
| context_mode | string | "auto" | Source: "auto", "subtitle", "slide", "both" |
| min_criticality | string | "medium" | Minimum criticality: "high", "medium", "low" |
| target_pages | int | 2 | Target length in pages (approximate) |
| subject_type | string | "auto" | Subject hint: "stem", "humanities", "auto" |

**Response:**
```json
{
  "content_id": "abc123",
  "content": "## Formulas & Constants\n\n...",
  "updated_at": "2025-01-27T10:35:00Z",
  "used_sources": ["subtitle", "slide"],
  "stats": {
    "total_items": 25,
    "by_category": {
      "formula": 10,
      "definition": 8,
      "condition": 4,
      "example": 3
    }
  }
}
```

## Output Format

Generated cheatsheets follow this structure:

```markdown
## Formulas & Constants

| Formula | Description |
|---------|-------------|
| $E=mc^2$ | Energy-mass equivalence |

## Key Definitions

- **Term**: Concise definition
  - Key condition or constraint

## Algorithms & Procedures

1. Step one
2. Step two

## Common Pitfalls

- Pitfall to avoid
```
