"use client";

import { JeromeluAvatar } from "./JeromeluAvatar";
import { useAvatarEngine } from "./AvatarEngine";

interface ConnectedAvatarProps {
  size?: number;
}

export function ConnectedAvatar({ size = 140 }: ConnectedAvatarProps) {
  const { state } = useAvatarEngine();
  return <JeromeluAvatar size={size} clipSrc={state.clipSrc} />;
}
