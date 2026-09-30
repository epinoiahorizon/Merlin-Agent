#!/usr/bin/env python3
# Merlin Dual-Pane TUI — interactive chat + live telemetry HUD (rich)
import sys
import time
import os
from typing import List, Dict
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.table import Table

console = Console()

class MerlinDualPaneTUI:
    def __init__(
        self,
        agent_name: str = "MERLIN_SPECTRE",
        model: str = "glm-5.3-flash",
        max_tokens: int = 8192,
        initial_tokens: int = 1420
    ):
        self.agent_name = agent_name
        self.model = model
        self.max_tokens = max_tokens
        self.cur_tokens = initial_tokens
        self.history: List[Dict[str, str]] = []
        self.status = "IDLE // READY"
        self.throughput = 98.4
        self.latency_ms = 11.2

    def get_token_bar(self, width: int = 16) -> str:
        ratio = min(max(self.cur_tokens / self.max_tokens, 0.0), 1.0)
        filled = int(ratio * width)
        return "■" * filled + "□" * (width - filled)

    def render_hud(self):
        # 1. Left Pane: Agent Identity & Arch
        left_body = (
            f"[bold white]MODEL  :[/] [cyan]{self.model}[/]\n"
            f"[bold white]ROLE   :[/] [yellow]TACTICAL_AUTONOMOUS_OPERATOR[/]\n"
            f"[bold white]PULSE  :[/] [green]O(log L) FUSED KOGGE SCAN[/]\n"
            f"[bold white]STATUS :[/] [bold magenta]{self.status}[/]"
        )
        left_panel = Panel(
            left_body,
            title=f"[bold cyan]╔═[ AGENT: {self.agent_name} ]═╗[/]",
            border_style="cyan",
            expand=True
        )

        # 2. Right Pane: Live Telemetry & Token Bar
        pct = (self.cur_tokens / self.max_tokens) * 100
        bar = self.get_token_bar(16)
        right_body = (
            f"[bold white]TOKEN LOAD :[/]\n"
            f"[bold green][{bar}][/] [cyan]{pct:.1f}%[/]\n"
            f"[bold white]USAGE      :[/] [white]{self.cur_tokens:,} / {self.max_tokens:,} tok[/]\n"
            f"[bold white]THROUGHPUT :[/] [green]{self.throughput} tok/s[/] | [yellow]LAT: {self.latency_ms}ms[/]"
        )
        right_panel = Panel(
            right_body,
            title="[bold green]╔═[ CONTEXT & METRICS ]═╗[/]",
            border_style="green",
            expand=True
        )

        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(left_panel, right_panel)
        console.print(grid)

    def render_history(self):
        if not self.history:
            empty_text = Text("\n  [ Belum ada interaksi. Masukkan prompt directive di bawah. ]\n", style="dim italic")
            console.print(Panel(empty_text, title="[bold white]CONVERSATION STREAM[/]", border_style="blue"))
            return

        stream_content = []
        for msg in self.history:
            role = msg["role"]
            content = msg["content"]
            timestamp = msg.get("time", "00:00:00")

            if role == "user":
                stream_content.append(f"\n[bold yellow]▲ USER [JM_OPERATOR][/][dim]────────────── {timestamp}[/]")
                stream_content.append(f"  \"{content}\"\n")
            elif role == "agent":
                thinking = msg.get("thinking", "")
                if thinking:
                    # Thinking / Cognitive Trace Box
                    trace_panel = Panel(
                        f"[dim]{thinking}[/]",
                        title="[bold magenta]┌─ [THINKING TRACE // COGNITIVE PULSE] ─┐[/]",
                        border_style="magenta",
                        padding=(0, 1)
                    )
                    stream_content.append(trace_panel)

                stream_content.append(f"[bold cyan]▼ AGENT [{self.agent_name}][/][dim]────────────── {timestamp}[/]")
                stream_content.append(f"  {content}\n")

        # Bungkus semua log di panel utama
        full_stream = Table.grid(expand=True)
        full_stream.add_column()
        for item in stream_content:
            full_stream.add_row(item)

        console.print(Panel(full_stream, title="[bold white]CONVERSATION STREAM[/]", border_style="blue"))

    def redraw(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.render_hud()
        self.render_history()

    def process_turn(self, user_prompt: str):
        now = time.strftime("%H:%M:%S")
        self.history.append({
            "role": "user",
            "content": user_prompt,
            "time": now
        })

        # Simulated Cognitive Phase
        self.status = "COGNITIVE_PULSE // THINKING"
        self.redraw()
        time.sleep(0.4)

        thinking_mock = (
            "1. Parse directive -> scan query & target architecture\n"
            "2. Profile SSM gate projection (x_proj -> dt_proj)\n"
            "3. Synthesize patch surgical in-place tanpa allocation overhead"
        )

        response_mock = (
            "Directive dieksekusi. Bottleneck O(L) di-bypass ke O(log L) via fused scan.\n"
            "Status: In-place memory locked, intermediate buffer dibersihkan."
        )

        # Update Tokens
        self.cur_tokens += len(user_prompt.split()) * 4 + 180
        self.status = "IDLE // READY"

        self.history.append({
            "role": "agent",
            "content": response_mock,
            "thinking": thinking_mock,
            "time": time.strftime("%H:%M:%S")
        })
        self.redraw()

    def run(self):
        self.redraw()
        while True:
            try:
                console.print("[bold green]├─ [DIRECTIVE INPUT] ──────────────────────────────────────────┤[/]")
                directive = console.input("[bold cyan]❯ [/][bold white]")
                if not directive.strip():
                    continue
                if directive.strip().lower() in ["exit", "quit", ":q"]:
                    console.print("\n[dim]Terminal session terminated.[/]")
                    break
                self.process_turn(directive)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Abort signal detected. Exiting...[/]")
                break

if __name__ == "__main__":
    tui = MerlinDualPaneTUI()
    tui.run()
