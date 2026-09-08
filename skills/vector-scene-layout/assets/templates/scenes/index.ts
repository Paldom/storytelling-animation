// Map every storyboard beat id to its scene component. Video.tsx throws on a
// missing entry so a forgotten beat fails the render instead of rendering blank.
import type React from "react";
import type { SceneProps } from "./Scene";
import { Headline } from "./Headline";

export const scenes: Record<string, React.FC<SceneProps>> = {
  hook: Headline,
  cta: Headline,
};
