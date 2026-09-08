import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { presence, rise } from "../motion";
import type { SceneProps } from "./Scene";
import storyboard from "../../storyboard.json";

// An animated text card: rises in over 0.4 s, holds still for the readable window,
// fades out over the last 0.3 s. Frame is local to the beat's Sequence.
export const TextCard: React.FC<SceneProps> = ({ beat, tokens }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const brand = storyboard.brand ?? {};
  const p = presence(frame, fps, beat.durationInFrames, { skipExit: beat.overlapOutFrames > 0 });
  return (
    <AbsoluteFill
      style={{
        padding: `${tokens.safe.top}px ${tokens.safe.right}px ${tokens.safe.bottom}px ${tokens.safe.left}px`,
        justifyContent: "center",
        alignItems: "center",
        fontFamily,
        color: brand.text ?? "#F5F7FF",
      }}
    >
      <div
        style={{
          ...rise(p, tokens.type.body),
          fontSize: tokens.type.headline,
          fontWeight: tokens.minWeight.headline,
          lineHeight: tokens.lineHeight,
          textAlign: "center",
          maxWidth: tokens.safeWidth,
          textWrap: "balance",
        }}
      >
        {beat.text}
      </div>
    </AbsoluteFill>
  );
};
