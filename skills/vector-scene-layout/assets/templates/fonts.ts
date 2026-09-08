// One font, loaded once. Scenes import { fontFamily }; Video.tsx awaits waitUntilDone()
// behind delayRender() so no frame renders in the fallback font.
import { loadFont } from "@remotion/google-fonts/Inter";

export const { fontFamily, waitUntilDone } = loadFont("normal", {
  weights: ["500", "700"],
  subsets: ["latin"],
});
