import { randomUUID } from 'crypto';

type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

interface Job {
  id: string;
  status: JobStatus;
  error?: string;
  startedAt?: Date;
  finishedAt?: Date;
}

interface QueuedTask {
  id: string;
  run: () => Promise<void>;
}

export class QuizJobQueue {
  private queue: QueuedTask[] = [];
  private jobs = new Map<string, Job>();
  private processing = false;
  private isInitialized = false;

  /**
   * Start the queue processor - call this on server startup
   */
  start(): void {
    if (this.isInitialized) return;
    this.isInitialized = true;
    console.log('🚀 Quiz job queue started');
    // Trigger processing in case there are already jobs
    setImmediate(() => this.processNext());
  }

  enqueue(task: () => Promise<void>): Job {
    const id = randomUUID();
    const job: Job = { id, status: 'queued' };
    this.jobs.set(id, job);
    this.queue.push({ id, run: task });
    this.processNext();
    return job;
  }

  getJob(jobId: string): Job | undefined {
    return this.jobs.get(jobId);
  }

  private async processNext(): Promise<void> {
    if (this.processing) return;
    const next = this.queue.shift();
    if (!next) return;

    this.processing = true;
    const job = this.jobs.get(next.id);
    if (job) {
      job.status = 'running';
      job.startedAt = new Date();
      console.log(`🏃 Starting quiz generation job ${job.id}`);
    }

    try {
      await next.run();
      if (job) {
        job.status = 'succeeded';
        console.log(`✅ Quiz generation job ${job.id} succeeded`);
      }
    } catch (error: any) {
      console.error(`❌ Quiz generation job ${job?.id} failed:`, error);
      if (job) {
        job.status = 'failed';
        job.error = error?.message ?? 'Unknown error';
      }
    } finally {
      if (job) {
        job.finishedAt = new Date();
      }
      this.processing = false;
      // Process the next task asynchronously to avoid deep recursion
      setImmediate(() => this.processNext());
    }
  }
}

export const quizJobQueue = new QuizJobQueue();
