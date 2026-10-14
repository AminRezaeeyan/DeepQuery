// Estimates how long linking a corpus takes for a given system.

interface SystemProfile {
  name: string;
  msPerForwardPass: number;
  passesPerDocument: (mentions: number) => number;
}

const SYSTEMS: SystemProfile[] = [
  // ReFinED encodes all mentions of a 512-token chunk in one pass.
  { name: "refined", msPerForwardPass: 65, passesPerDocument: () => 1 },
  // A bi-encoder encodes each mention separately.
  { name: "bi-encoder", msPerForwardPass: 20, passesPerDocument: (m) => m },
  // A cross-encoder encodes each mention with each of its 30 candidates.
  { name: "cross-encoder", msPerForwardPass: 10, passesPerDocument: (m) => m * 30 },
];

export function corpusHours(system: SystemProfile, documents: number, mentionsPerDocument: number): number {
  const ms = documents * system.passesPerDocument(mentionsPerDocument) * system.msPerForwardPass;
  return ms / 1000 / 3600;
}

for (const system of SYSTEMS) {
  console.log(`${system.name}: ${corpusHours(system, 1_000_000, 25).toFixed(1)} h`);
}
