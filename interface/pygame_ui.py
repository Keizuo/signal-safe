"""Polished Pygame interface for Signal Safe.

The interface adds visual hierarchy, progress feedback, streaks, keyboard shortcuts,
and a clearer post-decision explanation while keeping the original game logic intact.
"""
import time
import pygame

from agents.factory import make_attacker
from config import GAME_TITLE, COMPANY_NAME, DEFAULT_ROUNDS
from evaluation.logger import GameLogger
from game.session import Session

WIDTH, HEIGHT = 1180, 790
FPS = 60

# Palette
BG = (11, 17, 32)
PANEL = (19, 29, 49)
PANEL_ALT = (24, 37, 60)
BORDER = (42, 59, 86)
WHITE = (239, 245, 255)
MUTED = (151, 169, 194)
CYAN = (66, 211, 229)
BLUE = (75, 129, 255)
GREEN = (64, 211, 150)
RED = (255, 105, 116)
AMBER = (255, 190, 92)
PURPLE = (174, 145, 255)


def rounded(surface, color, rect, radius=14, border=None, border_width=1):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


def draw_text(surface, text, font, color, pos, anchor="topleft"):
    rendered = font.render(str(text), True, color)
    rect = rendered.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(rendered, rect)
    return rect


def wrap_text(text, font, max_width):
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(surface, text, font, color, x, y, max_width, line_gap=7, max_lines=8):
    lines = wrap_text(text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    for line in lines:
        surface.blit(font.render(line, True, color), (x, y))
        y += font.get_linesize() + line_gap
    return y


def draw_button(surface, rect, title, subtitle, accent, hovered, number):
    fill = (31, 48, 75) if hovered else PANEL_ALT
    border = accent if hovered else BORDER
    rounded(surface, fill, rect, 13, border, 2 if hovered else 1)
    pygame.draw.circle(surface, accent, (rect.x + 25, rect.centery), 13)
    draw_text(surface, number, pygame.font.SysFont("arial", 14, bold=True), BG,
              (rect.x + 25, rect.centery), "center")
    draw_text(surface, title, pygame.font.SysFont("arial", 18, bold=True), WHITE,
              (rect.x + 49, rect.y + 13))
    draw_text(surface, subtitle, pygame.font.SysFont("arial", 12), MUTED,
              (rect.x + 49, rect.y + 39))


def run_pygame(rounds=DEFAULT_ROUNDS, agent_type="full", seed=None, player_id="human"):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(GAME_TITLE)
    clock = pygame.time.Clock()

    font_xl = pygame.font.SysFont("arial", 31, bold=True)
    font_lg = pygame.font.SysFont("arial", 23, bold=True)
    font_md = pygame.font.SysFont("arial", 17)
    font_sm = pygame.font.SysFont("arial", 14)
    font_xs = pygame.font.SysFont("arial", 12)

    rounds = max(1, rounds)
    # All game logic (attacker, player model, scoring, logging) lives in Session,
    # shared with the terminal game and the simulator.
    session = Session(make_attacker(agent_type, seed), rounds=rounds, seed=seed,
                      logger=GameLogger(), agent_type=agent_type, player_id=player_id)
    state = session.state

    current = None
    started = time.perf_counter()
    feedback = None
    finished = False
    streak = 0
    best_streak = 0
    total_decision_time = 0.0
    last_points = 0
    pulse = 0.0

    # Main content and response buttons
    buttons = [
        pygame.Rect(48, 628, 260, 78),
        pygame.Rect(324, 628, 260, 78),
        pygame.Rect(600, 628, 260, 78),
        pygame.Rect(876, 628, 260, 78),
    ]
    actions = [
        ("Trust / Comply", "Only if the request is expected", AMBER, "trust"),
        ("Verify", "Check through another channel", CYAN, "verify"),
        ("Report", "Flag the message for review", RED, "report"),
        ("Ignore", "Take no action", PURPLE, "ignore"),
    ]

    def next_scenario():
        nonlocal current, started, feedback
        current = session.next_scenario()      # None when the session is over
        started = time.perf_counter()
        feedback = None

    def draw_background():
        screen.fill(BG)
        # Subtle decorative grid
        for x in range(0, WIDTH, 48):
            pygame.draw.line(screen, (16, 25, 43), (x, 0), (x, HEIGHT), 1)
        for y in range(0, HEIGHT, 48):
            pygame.draw.line(screen, (16, 25, 43), (0, y), (WIDTH, y), 1)

    def draw_stat_card(rect, label, value, accent):
        rounded(screen, PANEL, rect, 12, BORDER)
        draw_text(screen, label.upper(), font_xs, MUTED, (rect.x + 15, rect.y + 12))
        draw_text(screen, value, font_lg, accent, (rect.x + 15, rect.y + 31))

    def draw_header():
        rounded(screen, PANEL, pygame.Rect(24, 18, WIDTH - 48, 72), 17, BORDER)
        # Logo mark
        rounded(screen, (26, 57, 83), pygame.Rect(42, 32, 43, 43), 12, CYAN, 1)
        draw_text(screen, "S", pygame.font.SysFont("arial", 24, bold=True), CYAN,
                  (63, 53), "center")
        draw_text(screen, "SIGNAL SAFE", font_lg, WHITE, (98, 31))
        draw_text(screen, "INBOX DEFENSE SIMULATOR", font_xs, MUTED, (99, 59))
        draw_text(screen, "NORTHSTAR  /  SECURITY TRAINING", font_xs, CYAN,
                  (WIDTH - 45, 54), "topright")

    def draw_progress():
        x, y, w, h = 48, 119, 1088, 9
        rounded(screen, (32, 47, 70), pygame.Rect(x, y, w, h), 5)
        progress = min(1.0, state.current_round / rounds)
        if progress > 0:
            rounded(screen, CYAN, pygame.Rect(x, y, max(8, int(w * progress)), h), 5)
        draw_text(screen, f"MISSION PROGRESS     {state.current_round:02d} / {rounds:02d}",
                  font_xs, MUTED, (48, 139))
        draw_text(screen, f"{int(progress * 100)}%", font_xs, CYAN, (1136, 139), "topright")

    def draw_round():
        draw_progress()
        draw_stat_card(pygame.Rect(48, 166, 185, 75), "Current score", f"{state.score} XP", CYAN)
        draw_stat_card(pygame.Rect(245, 166, 185, 75), "Accuracy", f"{state.accuracy:.0f}%", GREEN)
        draw_stat_card(pygame.Rect(442, 166, 185, 75), "Current streak", f"{streak}  ×", AMBER)
        draw_stat_card(pygame.Rect(639, 166, 185, 75), "Best streak", f"{best_streak}  ×", PURPLE)
        elapsed = max(0, int(time.perf_counter() - started))
        draw_stat_card(pygame.Rect(836, 166, 300, 75), "Decision time", f"{elapsed:02d}s", WHITE)

        # Message card
        card = pygame.Rect(48, 260, 1088, 343)
        rounded(screen, PANEL, card, 18, BORDER)
        # Card heading
        channel = str(current.get("channel", "message")).upper()
        rounded(screen, (27, 54, 76), pygame.Rect(72, 282, 118, 28), 8)
        draw_text(screen, channel, font_xs, CYAN, (131, 296), "center")
        draw_text(screen, f"INCOMING MESSAGE   /   CASE {(state.current_round if feedback else state.current_round + 1):02d}",
                  font_xs, MUTED, (210, 290))
        draw_text(screen, "Review this message carefully", font_lg, WHITE, (72, 329))

        # Sender details
        rounded(screen, PANEL_ALT, pygame.Rect(72, 374, 1040, 67), 11)
        initials = "".join(part[0] for part in str(current["sender"]).split()[:2]).upper()
        pygame.draw.circle(screen, (47, 75, 111), (106, 407), 20)
        draw_text(screen, initials or "?", font_sm, CYAN, (106, 407), "center")
        draw_text(screen, current["sender"], font_md, WHITE, (140, 386))
        draw_text(screen, f"Subject: {current['subject']}", font_sm, MUTED, (140, 411))
        draw_text(screen, "UNVERIFIED", font_xs, AMBER, (1088, 406), "midright")

        draw_text(screen, "MESSAGE CONTENT", font_xs, MUTED, (74, 463))
        draw_wrapped(screen, current["message"], font_md, WHITE, 74, 489, 1000,
                     line_gap=8, max_lines=4)

        if feedback:
            good = bool(feedback["correct"])
            accent = GREEN if good else RED
            rounded(screen, (24, 49, 56) if good else (59, 36, 49),
                    pygame.Rect(48, 615, 1088, 94), 15, accent, 1)
            draw_text(screen, feedback["title"], font_md, accent, (70, 630))
            draw_text(screen, feedback["points"], font_lg, WHITE, (1110, 628), "topright")
            draw_wrapped(screen, feedback["explanation"], font_sm, MUTED,
                         70, 657, 1010, line_gap=3, max_lines=2)
            draw_text(screen, "PRESS SPACE  →  NEXT CASE", font_xs, CYAN,
                      (WIDTH // 2, 735), "center")
        else:
            draw_text(screen, "CHOOSE YOUR RESPONSE", font_xs, MUTED, (48, 613))
            mouse = pygame.mouse.get_pos()
            for i, (rect, (title, subtitle, accent, _action)) in enumerate(zip(buttons, actions)):
                draw_button(screen, rect, title, subtitle, accent,
                            rect.collidepoint(mouse), str(i + 1))
            draw_text(screen, "TIP: Use keys 1–4 for quick decisions",
                      font_xs, MUTED, (WIDTH // 2, 731), "center")

    def draw_finished():
        rounded(screen, PANEL, pygame.Rect(110, 145, 960, 520), 22, BORDER)
        pygame.draw.circle(screen, (27, 70, 77), (WIDTH // 2, 225), 43)
        draw_text(screen, "✓", pygame.font.SysFont("arial", 42, bold=True), GREEN,
                  (WIDTH // 2, 225), "center")
        draw_text(screen, "MISSION COMPLETE", font_xl, WHITE, (WIDTH // 2, 300), "center")
        draw_text(screen, "Your inbox defense report is ready.", font_md, MUTED,
                  (WIDTH // 2, 337), "center")

        stats = [
            ("FINAL SCORE", f"{state.score} XP", CYAN),
            ("ACCURACY", f"{state.accuracy:.1f}%", GREEN),
            ("BEST STREAK", f"{best_streak} ×", AMBER),
        ]
        for i, (label, value, accent) in enumerate(stats):
            rect = pygame.Rect(175 + i * 280, 390, 250, 100)
            rounded(screen, PANEL_ALT, rect, 14, BORDER)
            draw_text(screen, label, font_xs, MUTED, (rect.centerx, rect.y + 23), "center")
            draw_text(screen, value, font_xl, accent, (rect.centerx, rect.y + 60), "center")

        draw_text(screen, f"Correct decisions: {state.correct_decisions}    |    "
                  f"Needs review: {state.incorrect_decisions}", font_md, WHITE,
                  (WIDTH // 2, 535), "center")
        draw_text(screen, "Round-by-round results saved to results/game_logs.csv",
                  font_sm, MUTED, (WIDTH // 2, 576), "center")
        draw_text(screen, "Press ESC or close the window to exit.",
                  font_sm, CYAN, (WIDTH // 2, 625), "center")

    next_scenario()
    running = True
    while running:
        pulse += 0.05
        draw_background()
        draw_header()

        if state.is_finished or current is None:
            draw_finished()
        else:
            draw_round()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif feedback and event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                next_scenario()
            elif current and not feedback:
                selected_action = None
                if event.type == pygame.KEYDOWN:
                    key_map = {pygame.K_1: "trust", pygame.K_2: "verify",
                               pygame.K_3: "report", pygame.K_4: "ignore"}
                    selected_action = key_map.get(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, (_title, _subtitle, _accent, action) in zip(buttons, actions):
                        if rect.collidepoint(event.pos):
                            selected_action = action
                            break

                if selected_action:
                    elapsed = time.perf_counter() - started
                    total_decision_time += elapsed
                    scored = session.submit(selected_action, elapsed)

                    if scored["is_correct"]:
                        streak += 1
                        best_streak = max(best_streak, streak)
                    else:
                        streak = 0

                    feedback = {
                        "correct": scored["is_correct"],
                        "title": "NICE CATCH — SAFE DECISION" if scored["is_correct"]
                                 else "CASE REVIEW — LEARN FROM THIS ONE",
                        "points": f"{scored['points']:+} XP",
                        "explanation": scored["feedback_text"],
                    }

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
