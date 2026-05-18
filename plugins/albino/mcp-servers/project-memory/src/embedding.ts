/**
 * Neural embedding using @huggingface/transformers.
 *
 * Generates dense 384-dimensional float32 vectors via the
 * Xenova/all-MiniLM-L6-v2 sentence-transformer model. The pipeline is
 * lazy-initialised once on first call and reused for subsequent calls.
 */

import { pipeline, type FeatureExtractionPipeline } from "@huggingface/transformers";

/** Dimensionality of the all-MiniLM-L6-v2 model output. */
export const EMBEDDING_DIM = 384;

/** The model used for embedding. */
const MODEL_ID = "Xenova/all-MiniLM-L6-v2";

let pipelineInstance: FeatureExtractionPipeline | null = null;

async function getPipeline(): Promise<FeatureExtractionPipeline> {
  if (!pipelineInstance) {
    pipelineInstance = (await pipeline("feature-extraction", MODEL_ID, {
      dtype: "fp32"
    })) as FeatureExtractionPipeline;
  }
  return pipelineInstance;
}

/**
 * Generate dense embeddings for an array of texts.
 * Returns one float32 vector per input text, each of length EMBEDDING_DIM (384).
 */
export async function embed(texts: string[]): Promise<number[][]> {
  if (texts.length === 0) {
    return [];
  }

  const extractor = await getPipeline();
  const output = await extractor(texts, { pooling: "mean", normalize: true });

  // output.tolist() returns number[][] — one row per input text
  const nested = output.tolist() as number[][];
  return nested;
}

/** Build the text that gets embedded for a memory record. */
export function memoryEmbedText(content: string, summary: string | null, tags: string[]): string {
  const parts: string[] = [content];
  if (summary) {
    parts.push(summary);
  }

  if (tags.length > 0) {
    parts.push(tags.join(" "));
  }

  return parts.join(" ");
}

/** Compute cosine similarity between two dense vectors. Range [-1, 1]. */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length || a.length === 0) {
    return 0;
  }

  let dot = 0;
  let magA = 0;
  let magB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i]! * b[i]!;
    magA += a[i]! * a[i]!;
    magB += b[i]! * b[i]!;
  }

  const denom = Math.sqrt(magA) * Math.sqrt(magB);
  if (denom === 0) {
    return 0;
  }

  return dot / denom;
}
