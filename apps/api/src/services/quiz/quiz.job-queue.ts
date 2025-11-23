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
    }

    try {
      await next.run();
      if (job) {
        job.status = 'succeeded';
      }
    } catch (error: any) {
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
