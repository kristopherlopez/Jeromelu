"use client";

import { ConnectedAvatar } from "./components/ConnectedAvatar";
import { ThoughtBubbles } from "./components/ThoughtBubbles";

const AVATAR_SIZE = 180;

export function HomeClient() {
  return (
    <div className="relative flex items-center justify-center -mb-24">
      {/* Avatar in the center — below bubbles in z-order */}
      <div className="absolute inset-0 z-0 flex items-center justify-center">
        <ConnectedAvatar size={AVATAR_SIZE} />
      </div>
      {/* Thought bubbles on top */}
      <div className="relative z-10">
        <ThoughtBubbles avatarSize={AVATAR_SIZE} />
      </div>
    </div>
  );
}
