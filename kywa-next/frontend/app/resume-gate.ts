// A window resize, dialog or short focus change is not a return from background.
export class ResumeGate {
  private awayAt: number | null = null;
  private pending = false;
  private readonly minimumMs: number;

  constructor(minimumMs = 30_000) { this.minimumMs = minimumMs; }

  leave(now: number) {
    if (this.awayAt === null) this.awayAt = now;
  }

  resume(now: number, busy = false): boolean {
    if (this.awayAt !== null) {
      this.pending ||= now - this.awayAt >= this.minimumMs;
      this.awayAt = null;
    }
    if (!this.pending || busy) return false;
    this.pending = false;
    return true;
  }
}
