import { describe, it, expect } from "vitest";
import {
    getAutoSwitchModeOnHide,
    getAutoSwitchModeOnShow,
    createAutoSwitchState,
    updateStateOnAutoSwitch,
    resetAutoSwitchState,
} from "../subtitleAutoSwitch";

describe("subtitleAutoSwitch", () => {
    describe("getAutoSwitchModeOnHide", () => {
        it("returns null when auto-switch is disabled", () => {
            const result = getAutoSwitchModeOnHide({
                enabled: false,
                hasTranslation: true,
                currentMode: "source",
            });
            expect(result).toBeNull();
        });

        it("returns null when no translation is available", () => {
            const result = getAutoSwitchModeOnHide({
                enabled: true,
                hasTranslation: false,
                currentMode: "source",
            });
            expect(result).toBeNull();
        });

        it("returns null when already on target mode", () => {
            const result = getAutoSwitchModeOnHide({
                enabled: true,
                hasTranslation: true,
                currentMode: "target",
            });
            expect(result).toBeNull();
        });

        it("switches source to target on hide", () => {
            const result = getAutoSwitchModeOnHide({
                enabled: true,
                hasTranslation: true,
                currentMode: "source",
            });
            expect(result).toBe("target");
        });

        it("switches dual to target on hide", () => {
            const result = getAutoSwitchModeOnHide({
                enabled: true,
                hasTranslation: true,
                currentMode: "dual",
            });
            expect(result).toBe("target");
        });

        it("switches dual_reversed to target on hide", () => {
            const result = getAutoSwitchModeOnHide({
                enabled: true,
                hasTranslation: true,
                currentMode: "dual_reversed",
            });
            expect(result).toBe("target");
        });
    });

    describe("getAutoSwitchModeOnShow", () => {
        it("returns null when auto-switch is disabled", () => {
            const state = updateStateOnAutoSwitch(createAutoSwitchState(), "source");
            const result = getAutoSwitchModeOnShow({
                enabled: false,
                hasTranslation: true,
                currentMode: "target",
                state,
            });
            expect(result).toBeNull();
        });

        it("returns null when was not auto-switched", () => {
            const result = getAutoSwitchModeOnShow({
                enabled: true,
                hasTranslation: true,
                currentMode: "target",
                state: createAutoSwitchState(),
            });
            expect(result).toBeNull();
        });

        it("returns null when user manually changed mode while away", () => {
            const state = updateStateOnAutoSwitch(createAutoSwitchState(), "source");
            const result = getAutoSwitchModeOnShow({
                enabled: true,
                hasTranslation: true,
                currentMode: "dual", // User changed to dual while away
                state,
            });
            expect(result).toBeNull();
        });

        it("restores previous mode when auto-switched and still on target", () => {
            const state = updateStateOnAutoSwitch(createAutoSwitchState(), "source");
            const result = getAutoSwitchModeOnShow({
                enabled: true,
                hasTranslation: true,
                currentMode: "target",
                state,
            });
            expect(result).toBe("source");
        });

        it("restores dual mode correctly", () => {
            const state = updateStateOnAutoSwitch(createAutoSwitchState(), "dual");
            const result = getAutoSwitchModeOnShow({
                enabled: true,
                hasTranslation: true,
                currentMode: "target",
                state,
            });
            expect(result).toBe("dual");
        });
    });

    describe("state management", () => {
        it("creates initial state with no previous mode and not auto-switched", () => {
            const state = createAutoSwitchState();
            expect(state.previousMode).toBeNull();
            expect(state.wasAutoSwitched).toBe(false);
        });

        it("updates state correctly on auto-switch", () => {
            const initialState = createAutoSwitchState();
            const newState = updateStateOnAutoSwitch(initialState, "dual_reversed");
            expect(newState.previousMode).toBe("dual_reversed");
            expect(newState.wasAutoSwitched).toBe(true);
        });

        it("resets state correctly", () => {
            const _state = updateStateOnAutoSwitch(createAutoSwitchState(), "source");
            const resetState = resetAutoSwitchState();
            expect(resetState.previousMode).toBeNull();
            expect(resetState.wasAutoSwitched).toBe(false);
        });
    });
});
