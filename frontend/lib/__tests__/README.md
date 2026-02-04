# Frontend Unit Tests

This directory contains unit tests for the frontend library modules.

## Test Framework

- **Vitest** - Fast Vite-native unit test framework
- Compatible with Jest API (`describe`, `it`, `expect`)

## Running Tests

```bash
# Run all tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Run specific test file
pnpm test subtitleAutoSwitch
```

## Test Organization

Tests are organized by module:

| Test File | Module Under Test | Description |
|-----------|-------------------|-------------|
| `subtitleAutoSwitch.test.ts` | `../subtitleAutoSwitch.ts` | Auto-switch state machine for subtitle mode changes |

## Writing Tests

### Conventions

1. **File naming**: `<module>.test.ts` mirrors `../<module>.ts`
2. **Test structure**: Use `describe` blocks to group related tests
3. **Test naming**: Use clear, behavior-focused names (e.g., "returns null when auto-switch is disabled")

### Example

```typescript
import { describe, it, expect } from "vitest";
import { myFunction } from "../myModule";

describe("myModule", () => {
    describe("myFunction", () => {
        it("returns expected value for valid input", () => {
            const result = myFunction({ validInput: true });
            expect(result).toBe("expected");
        });

        it("returns null for invalid input", () => {
            const result = myFunction({ validInput: false });
            expect(result).toBeNull();
        });
    });
});
```

## Coverage

Pure functions in `/lib` should have high test coverage as they contain core business logic decoupled from React.
