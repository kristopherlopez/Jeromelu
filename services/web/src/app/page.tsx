import JeromeluLogo from "./components/JeromeluLogo";

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-black">
      <main className="flex flex-col items-center gap-8 text-center">
        <JeromeluLogo />
        <div className="flex items-center gap-2 rounded-full border border-zinc-800 px-4 py-2 text-sm text-zinc-500">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--tigers-orange)] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--tigers-orange)]" />
          </span>
          Watching the market
        </div>
      </main>
    </div>
  );
}
