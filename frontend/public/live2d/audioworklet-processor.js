/**
 * AudioWorklet Processor for MotionSync
 * Captures real-time audio samples from microphone input
 *
 * Based on Live2D Cubism SDK sample code
 */

class MotionSyncAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.useChannel = 0;
  }

  process(inputs, outputs, parameters) {
    const channel = this.useChannel % inputs[0].length;
    const input = inputs[0][channel];

    if (input == undefined || input == null) {
      return true;
    }

    // Send audio buffer to main thread
    const audioBuffer = Float32Array.from([...input]);
    this.port.postMessage({
      eventType: "data",
      audioBuffer: audioBuffer,
    });

    // Pass through audio to output (for monitoring if needed)
    let inputArray = inputs[0];
    let output = outputs[0];
    for (let currentChannel = 0; currentChannel < inputArray.length; ++currentChannel) {
      let inputChannel = inputArray[currentChannel];
      let outputChannel = output[currentChannel];
      for (let i = 0; i < inputChannel.length; ++i) {
        outputChannel[i] = inputChannel[i];
      }
    }

    return true;
  }
}

registerProcessor('motionsync-audio-processor', MotionSyncAudioProcessor);
