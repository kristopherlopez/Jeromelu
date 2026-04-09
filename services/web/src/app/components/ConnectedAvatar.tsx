"use client";

import { JeromeluAvatar } from "./JeromeluAvatar";
import { useAvatarEngine } from "./AvatarEngine";

interface ConnectedAvatarProps {
  size?: number;
  light?: boolean;
}

export function ConnectedAvatar({ size = 140, light }: ConnectedAvatarProps) {
  const { state } = useAvatarEngine();
  return <JeromeluAvatar size={size} clipSrc={state.clipSrc} light={light} />;
}
