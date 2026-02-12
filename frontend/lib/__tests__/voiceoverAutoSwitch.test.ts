import { describe, it, expect } from "vitest";
import {
    getAutoSwitchVoiceoverOnHide,
    getAutoSwitchVoiceoverOnShow,
    createVoiceoverAutoSwitchState,
    updateStateOnVoiceoverAutoSwitch,
    resetVoiceoverAutoSwitchState,
} from "../voiceoverAutoSwitch";

describe("voiceoverAutoSwitch", () => {
    describe("getAutoSwitchVoiceoverOnHide", () => {
        it("returns undefined when auto-switch is disabled", () => {
            const result = getAutoSwitchVoiceoverOnHide({
                enabled: false,
                selectedVoiceoverId: null,
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
            });
            expect(result).toBeUndefined();
        });

        it("returns undefined when translated preset is not configured", () => {
            const result = getAutoSwitchVoiceoverOnHide({
                enabled: true,
                selectedVoiceoverId: null,
                originalVoiceoverId: null,
                translatedVoiceoverId: null,
            });
            expect(result).toBeUndefined();
        });

        it("returns undefined when already on translated preset", () => {
            const result = getAutoSwitchVoiceoverOnHide({
                enabled: true,
                selectedVoiceoverId: "translated-1",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
            });
            expect(result).toBeUndefined();
        });

        it("returns undefined when current track is neither original nor translated preset", () => {
            const result = getAutoSwitchVoiceoverOnHide({
                enabled: true,
                selectedVoiceoverId: "custom-voiceover",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
            });
            expect(result).toBeUndefined();
        });

        it("switches from original preset to translated preset", () => {
            const result = getAutoSwitchVoiceoverOnHide({
                enabled: true,
                selectedVoiceoverId: null,
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
            });
            expect(result).toBe("translated-1");
        });
    });

    describe("getAutoSwitchVoiceoverOnShow", () => {
        it("returns undefined when auto-switch is disabled", () => {
            const state = updateStateOnVoiceoverAutoSwitch(null);
            const result = getAutoSwitchVoiceoverOnShow({
                enabled: false,
                selectedVoiceoverId: "translated-1",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
                state,
            });
            expect(result).toBeUndefined();
        });

        it("returns undefined when was not auto-switched", () => {
            const result = getAutoSwitchVoiceoverOnShow({
                enabled: true,
                selectedVoiceoverId: "translated-1",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
                state: createVoiceoverAutoSwitchState(),
            });
            expect(result).toBeUndefined();
        });

        it("returns undefined when user manually changed voiceover while away", () => {
            const state = updateStateOnVoiceoverAutoSwitch(null);
            const result = getAutoSwitchVoiceoverOnShow({
                enabled: true,
                selectedVoiceoverId: "custom-voiceover",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
                state,
            });
            expect(result).toBeUndefined();
        });

        it("restores previous voiceover when auto-switched", () => {
            const state = updateStateOnVoiceoverAutoSwitch(null);
            const result = getAutoSwitchVoiceoverOnShow({
                enabled: true,
                selectedVoiceoverId: "translated-1",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
                state,
            });
            expect(result).toBeNull();
        });

        it("restores previous custom voiceover id", () => {
            const state = updateStateOnVoiceoverAutoSwitch("custom-voiceover");
            const result = getAutoSwitchVoiceoverOnShow({
                enabled: true,
                selectedVoiceoverId: "translated-1",
                originalVoiceoverId: null,
                translatedVoiceoverId: "translated-1",
                state,
            });
            expect(result).toBe("custom-voiceover");
        });
    });

    describe("state management", () => {
        it("creates initial state", () => {
            const state = createVoiceoverAutoSwitchState();
            expect(state.previousVoiceoverId).toBeNull();
            expect(state.wasAutoSwitched).toBe(false);
        });

        it("updates state on auto-switch", () => {
            const state = updateStateOnVoiceoverAutoSwitch("original-1");
            expect(state.previousVoiceoverId).toBe("original-1");
            expect(state.wasAutoSwitched).toBe(true);
        });

        it("resets state", () => {
            const state = resetVoiceoverAutoSwitchState();
            expect(state.previousVoiceoverId).toBeNull();
            expect(state.wasAutoSwitched).toBe(false);
        });
    });
});
