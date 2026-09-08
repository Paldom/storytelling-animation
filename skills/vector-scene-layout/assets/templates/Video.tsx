import React, { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { beats, LOOP } from "./timeline";
import { tokensFor } from "./tokens";
import { waitUntilDone } from "./fonts";
import { scenes } from "./scenes";
import storyboard from "../storyboard.json";

export type VideoProps = { target: string };

// One element per transition type keeps the presentation generics typed without casts.
const transitionFor = (key: string, type: string, durationInFrames: number) => {
  const timing = linearTiming({ durationInFrames });
  if (type === "slide") {
    return <TransitionSeries.Transition key={key} timing={timing} presentation={slide({ direction: "from-right" })} />;
  }
  if (type === "wipe") {
    return <TransitionSeries.Transition key={key} timing={timing} presentation={wipe({ direction: "from-left" })} />;
  }
  // fade and morph; morph is refined in the motion step
  return <TransitionSeries.Transition key={key} timing={timing} presentation={fade()} />;
};

export const Video: React.FC<VideoProps> = ({ target }) => {
  const tokens = tokensFor(target);
  const [handle] = useState(() => delayRender("fonts"));
  useEffect(() => {
    waitUntilDone().then(() => continueRender(handle));
  }, [handle]);
  const background = storyboard.brand?.background ?? "#0B1020";

  const items: React.ReactNode[] = [];
  beats.forEach((beat, i) => {
    const Scene = scenes[beat.id];
    if (!Scene) throw new Error(`no scene component registered for beat "${beat.id}"`);
    items.push(
      <TransitionSeries.Sequence key={beat.id} durationInFrames={beat.durationInFrames}>
        <Scene beat={beat} tokens={tokens} />
      </TransitionSeries.Sequence>,
    );
    const hasNext = i < beats.length - 1;
    // The wrap transition of a loop is built in the motion step; here it is skipped.
    if (beat.overlapOutFrames > 0 && (hasNext || !LOOP)) {
      items.push(transitionFor(`${beat.id}-t`, beat.transitionType, beat.overlapOutFrames));
    }
  });

  return (
    <AbsoluteFill style={{ backgroundColor: background }}>
      <TransitionSeries>{items}</TransitionSeries>
    </AbsoluteFill>
  );
};
