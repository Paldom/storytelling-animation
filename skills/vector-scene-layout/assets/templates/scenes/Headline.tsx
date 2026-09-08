import React from "react";
import { AbsoluteFill } from "remotion";
import { fontFamily } from "../fonts";
import type { SceneProps } from "./Scene";
import storyboard from "../../storyboard.json";

// A static scene: text card inside the safe area, sizes from tokens, nothing
// hard-coded. Motion is added in the choreography step; keep this frame-independent.
export const Headline: React.FC<SceneProps> = ({ beat, tokens }) => {
  const brand = storyboard.brand ?? {};
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
