// Returns the bot answer for a question (dummy for now, the real backend call comes later)
export async function askBot(question: string): Promise<string> {
  await new Promise((resolve) => setTimeout(resolve, 600));
  return `Kamu bertanya: "${question}". Jawaban asli muncul setelah tersambung ke backend.`;
}