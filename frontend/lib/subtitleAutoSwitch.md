# subtitleAutoSwitch

Pure functions for managing subtitle auto-switch behavior when the user leaves/returns to the page.

## Overview

This module handles the automatic switching of subtitles to "target" (translated) mode when the user leaves the page (for background listening), and restores the previous mode when they return.

## External Interface

### Types

```typescript
interface AutoSwitchState {
    /** The subtitle mode before auto-switch occurred */
    previousMode: SubtitleDisplayMode | null;
    /** Whether the last mode change was due to auto-switch (vs manual user action) */
    wasAutoSwitched: boolean;
}

interface AutoSwitchContext {
    enabled: boolean;
    hasTranslation: boolean;
    currentMode: SubtitleDisplayMode;
    state: AutoSwitchState;
}
```

### Functions

#### `getAutoSwitchModeOnHide(ctx): SubtitleDisplayMode | null`

Determines if subtitles should switch when the page becomes hidden.

**Parameter**: `ctx` is `Omit<AutoSwitchContext, "state">` (state not needed for hide logic)

- Returns `"target"` if auto-switch should occur
- Returns `null` if no switch needed (disabled, no translation, or already on target)

#### `getAutoSwitchModeOnShow(ctx): SubtitleDisplayMode | null`

Determines the mode to restore when the page becomes visible.

**Parameter**: `ctx` is full `AutoSwitchContext` (needs state to check if was auto-switched)

- Returns the previous mode if it should be restored
- Returns `null` if no restore needed (disabled, wasn't auto-switched, or user manually changed mode while away)

#### `createAutoSwitchState(): AutoSwitchState`

Creates the initial state with no previous mode and `wasAutoSwitched: false`.

#### `updateStateOnAutoSwitch(previousMode): AutoSwitchState`

Creates new state recording that auto-switch occurred and what the previous mode was.

#### `resetAutoSwitchState(): AutoSwitchState`

Resets state after restore or manual override.

## Usage Example

```typescript
import {
    createAutoSwitchState,
    getAutoSwitchModeOnHide,
    getAutoSwitchModeOnShow,
    updateStateOnAutoSwitch,
    resetAutoSwitchState,
} from "@/lib/subtitleAutoSwitch";

// In a React component
const [autoSwitchState, setAutoSwitchState] = useState(createAutoSwitchState);

// On page hide (visibilitychange)
const newMode = getAutoSwitchModeOnHide({ enabled, hasTranslation, currentMode });
if (newMode) {
    setAutoSwitchState(updateStateOnAutoSwitch(currentMode));
    setSubtitleMode(newMode);
}

// On page show
const restoreMode = getAutoSwitchModeOnShow({ enabled, hasTranslation, currentMode, state: autoSwitchState });
if (restoreMode) {
    setSubtitleMode(restoreMode);
}
setAutoSwitchState(resetAutoSwitchState());
```

## Design Rationale

### Why Pure Functions?

The logic is implemented as pure functions to:
1. Enable comprehensive unit testing without React dependencies
2. Make the state machine explicit and predictable
3. Allow reuse in different UI frameworks if needed

### Debounce Strategy

The consumer (FocusModeHandler) applies a 1.5s debounce before triggering auto-switch on hide. This prevents rapid switching when users briefly tab away (e.g., to check a notification). The debounce is implemented manually with `setTimeout` rather than using a utility because:
1. We need cancellation on return (clearing timeout when page becomes visible)
2. The debounce only applies to hide, not show (asymmetric behavior)
