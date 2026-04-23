from __future__ import annotations

import argparse
import array
import math
import random
from dataclasses import dataclass, field
from typing import Final

try:
    import pygame
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local machine
    raise SystemExit(
        "This game needs pygame (or pygame-ce).\n"
        "Install it with:\n"
        "  python -m pip install pygame-ce"
    ) from exc

WIDTH: Final[int] = 800
HEIGHT: Final[int] = 600
TITLE: Final[str] = "AC'S Pong 0.1 infdev"
TARGET_FPS: Final[int] = 120
WINNING_SCORE: Final[int] = 5

BLACK: Final[tuple[int, int, int]] = (0, 0, 0)
WHITE: Final[tuple[int, int, int]] = (255, 255, 255)
GREEN: Final[tuple[int, int, int]] = (0, 255, 140)
RED: Final[tuple[int, int, int]] = (255, 90, 90)
CYAN: Final[tuple[int, int, int]] = (120, 235, 255)
GRAY: Final[tuple[int, int, int]] = (130, 130, 130)
DARK: Final[tuple[int, int, int]] = (16, 18, 24)
MID: Final[tuple[int, int, int]] = (40, 48, 58)
GOLD: Final[tuple[int, int, int]] = (255, 214, 102)

PADDLE_W: Final[int] = 14
PADDLE_H: Final[int] = 96
BALL_SIZE: Final[int] = 14
PADDLE_MARGIN: Final[int] = 28

SERVE_DELAY: Final[float] = 0.9
MIN_BALL_SPEED_X: Final[float] = 410.0
MAX_BALL_SPEED_X: Final[float] = 900.0
HIT_ACCELERATION: Final[float] = 1.065
MAX_FRAME_DT: Final[float] = 1 / 30

MENU_ITEMS: Final[list[str]] = [
    "Play Game",
    "Difficulty",
    "How to Play",
    "Credits",
    "About",
    "Exit",
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(slots=True)
class Difficulty:
    name: str
    ai_speed: float
    ai_deadzone: float
    ai_error: float
    ai_reaction: float


@dataclass(slots=True)
class Paddle:
    x: float
    y: float
    w: int
    h: int
    speed: float
    velocity: float = 0.0
    flash: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def center_y(self) -> float:
        return self.y + self.h / 2


@dataclass(slots=True)
class TrailNode:
    x: float
    y: float
    size: float
    life: float


@dataclass(slots=True)
class Ball:
    x: float
    y: float
    size: int
    vx: float
    vy: float
    trail: list[TrailNode] = field(default_factory=list)
    glow: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.size, self.size)

    @property
    def center_y(self) -> float:
        return self.y + self.size / 2

    def clear_trail(self) -> None:
        self.trail.clear()


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    size: float
    color: tuple[int, int, int]


@dataclass(slots=True)
class Star:
    x: float
    y: float
    speed: float
    size: int


class DynamicSoundEngine:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self.paddle_low: pygame.mixer.Sound | None = None
        self.paddle_high: pygame.mixer.Sound | None = None
        self.wall: pygame.mixer.Sound | None = None
        self.score: pygame.mixer.Sound | None = None
        self.menu: pygame.mixer.Sound | None = None
        self.win: pygame.mixer.Sound | None = None
        self.pause: pygame.mixer.Sound | None = None

        if not enabled:
            return

        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
        except pygame.error:
            return

        self.enabled = True
        self.paddle_low = self._make_tone(220, 55, 0.34, "square")
        self.paddle_high = self._make_tone(430, 45, 0.30, "square")
        self.wall = self._make_tone(160, 40, 0.22, "triangle")
        self.score = self._make_tone(110, 160, 0.40, "square")
        self.menu = self._make_tone(520, 35, 0.18, "square")
        self.win = self._make_tone(660, 200, 0.27, "triangle")
        self.pause = self._make_tone(280, 70, 0.16, "triangle")

    def _make_tone(
        self,
        freq: float,
        duration_ms: int,
        volume: float,
        wave_type: str = "square",
        decay: bool = True,
    ) -> pygame.mixer.Sound | None:
        sample_rate = 22050
        n_samples = int(sample_rate * (duration_ms / 1000.0))
        buf = array.array("h")

        for index in range(n_samples):
            t = index / sample_rate
            envelope = 1.0
            if decay:
                envelope = max(0.0, 1.0 - (index / max(1, n_samples - 1)))

            if wave_type == "square":
                sample = 1.0 if math.sin(2.0 * math.pi * freq * t) >= 0 else -1.0
            elif wave_type == "triangle":
                sample = (2.0 / math.pi) * math.asin(math.sin(2.0 * math.pi * freq * t))
            else:
                sample = math.sin(2.0 * math.pi * freq * t)

            buf.append(int(32767 * volume * envelope * sample))

        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, sound: pygame.mixer.Sound | None) -> None:
        if self.enabled and sound is not None:
            sound.play()

    def play_menu_move(self) -> None:
        self.play(self.menu)

    def play_paddle_hit(self, speed_mag: float) -> None:
        if not self.enabled:
            return
        self.play(self.paddle_low if speed_mag < 640 else self.paddle_high)

    def play_wall_hit(self) -> None:
        self.play(self.wall)

    def play_score(self) -> None:
        self.play(self.score)

    def play_win(self) -> None:
        self.play(self.win)

    def play_pause(self) -> None:
        self.play(self.pause)


class Game:
    def __init__(self, *, mute: bool = False, smoke_test: bool = False) -> None:
        pygame.init()
        pygame.display.init()

        self.flags = 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), self.flags)
        pygame.display.set_caption(TITLE)
        try:
            pygame.display.set_icon(self._make_icon_surface())
        except pygame.error:
            pass

        self.canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
        self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "menu"
        self.menu_index = 0
        self.paused = False
        self.fullscreen = False
        self.smoke_test = smoke_test
        self.smoke_frames_remaining = 8 if smoke_test else 0

        self.title_font = pygame.font.SysFont("Arial", 82, bold=True)
        self.menu_font = pygame.font.SysFont("Arial", 40)
        self.small_font = pygame.font.SysFont("Arial", 28)
        self.tiny_font = pygame.font.SysFont("Arial", 20)
        self.huge_font = pygame.font.SysFont("Arial", 120, bold=True)

        self.sfx = DynamicSoundEngine(enabled=not mute)

        self.difficulties: list[Difficulty] = [
            Difficulty("Rookie", ai_speed=410.0, ai_deadzone=18.0, ai_error=42.0, ai_reaction=0.09),
            Difficulty("Arcade", ai_speed=520.0, ai_deadzone=12.0, ai_error=18.0, ai_reaction=0.05),
            Difficulty("Insane", ai_speed=640.0, ai_deadzone=8.0, ai_error=4.0, ai_reaction=0.025),
        ]
        self.difficulty_index = 1

        self.player = Paddle(PADDLE_MARGIN, HEIGHT / 2 - PADDLE_H / 2, PADDLE_W, PADDLE_H, 540.0)
        self.ai = Paddle(WIDTH - PADDLE_MARGIN - PADDLE_W, HEIGHT / 2 - PADDLE_H / 2, PADDLE_W, PADDLE_H, 0.0)
        self.ball = Ball(WIDTH / 2 - BALL_SIZE / 2, HEIGHT / 2 - BALL_SIZE / 2, BALL_SIZE, 0.0, 0.0)

        self.player_score = 0
        self.ai_score = 0
        self.winner_text = ""
        self.winner_color = GREEN
        self.serve_timer = 0.0
        self.serve_direction = random.choice([-1, 1])
        self.score_flash_timer = 0.0
        self.point_text = ""
        self.point_text_timer = 0.0
        self.screen_shake_timer = 0.0
        self.screen_shake_strength = 0.0
        self.ai_think_timer = 0.0
        self.ai_target_y = self.ai.y

        self.particles: list[Particle] = []
        self.stars = self._build_starfield(72)

        self.reset_match(play_sound=False)

    def _make_icon_surface(self) -> pygame.Surface:
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        icon.fill((0, 0, 0, 0))
        pygame.draw.rect(icon, GREEN, (2, 6, 6, 20), border_radius=2)
        pygame.draw.rect(icon, CYAN, (24, 6, 6, 20), border_radius=2)
        pygame.draw.rect(icon, WHITE, (13, 13, 6, 6))
        return icon

    def _build_starfield(self, count: int) -> list[Star]:
        stars: list[Star] = []
        for _ in range(count):
            stars.append(
                Star(
                    x=random.uniform(0, WIDTH),
                    y=random.uniform(0, HEIGHT),
                    speed=random.uniform(12.0, 42.0),
                    size=random.choice([1, 1, 1, 2]),
                )
            )
        return stars

    @property
    def difficulty(self) -> Difficulty:
        return self.difficulties[self.difficulty_index]

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.flags = pygame.FULLSCREEN if self.fullscreen else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), self.flags)

    def reset_match(self, *, play_sound: bool = False) -> None:
        self.player_score = 0
        self.ai_score = 0
        self.player.y = HEIGHT / 2 - self.player.h / 2
        self.ai.y = HEIGHT / 2 - self.ai.h / 2
        self.player.velocity = 0.0
        self.ai.velocity = 0.0
        self.ball.clear_trail()
        self.particles.clear()
        self.score_flash_timer = 0.0
        self.point_text = ""
        self.point_text_timer = 0.0
        self.ai_think_timer = 0.0
        self.ai_target_y = self.ai.y
        self.reset_round(direction=random.choice([-1, 1]), play_sound=play_sound)

    def reset_round(self, *, direction: int, play_sound: bool = False) -> None:
        self.ball.x = WIDTH / 2 - self.ball.size / 2
        self.ball.y = HEIGHT / 2 - self.ball.size / 2
        self.ball.vx = MIN_BALL_SPEED_X * direction
        self.ball.vy = random.choice([-220.0, -160.0, 160.0, 220.0])
        self.ball.clear_trail()
        self.serve_direction = direction
        self.serve_timer = SERVE_DELAY
        if play_sound:
            self.sfx.play_score()

    def change_difficulty(self, step: int) -> None:
        self.difficulty_index = (self.difficulty_index + step) % len(self.difficulties)
        self.sfx.play_menu_move()

    def start_game(self) -> None:
        self.paused = False
        self.state = "match"
        self.reset_match(play_sound=False)

    def shake(self, strength: float, duration: float) -> None:
        self.screen_shake_strength = max(self.screen_shake_strength, strength)
        self.screen_shake_timer = max(self.screen_shake_timer, duration)

    def spawn_particles(
        self,
        x: float,
        y: float,
        *,
        color: tuple[int, int, int],
        count: int,
        base_speed: float,
    ) -> None:
        for _ in range(count):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(base_speed * 0.45, base_speed)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=random.uniform(0.18, 0.45),
                    size=random.uniform(2.0, 4.5),
                    color=color,
                )
            )

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                    continue

                if self.state == "menu":
                    self._handle_menu_key(event.key)
                elif self.state in {"how", "credits", "about"}:
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
                        self.sfx.play_menu_move()
                        self.state = "menu"
                elif self.state == "match":
                    self._handle_match_key(event.key)
                elif self.state == "winner":
                    self._handle_winner_key(event.key)

    def _handle_menu_key(self, key: int) -> None:
        if key == pygame.K_UP:
            self.menu_index = (self.menu_index - 1) % len(MENU_ITEMS)
            self.sfx.play_menu_move()
            return
        if key == pygame.K_DOWN:
            self.menu_index = (self.menu_index + 1) % len(MENU_ITEMS)
            self.sfx.play_menu_move()
            return
        if key in (pygame.K_LEFT, pygame.K_a) and MENU_ITEMS[self.menu_index] == "Difficulty":
            self.change_difficulty(-1)
            return
        if key in (pygame.K_RIGHT, pygame.K_d) and MENU_ITEMS[self.menu_index] == "Difficulty":
            self.change_difficulty(1)
            return
        if key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            return

        self.sfx.play_menu_move()
        choice = MENU_ITEMS[self.menu_index]
        if choice == "Play Game":
            self.start_game()
        elif choice == "Difficulty":
            self.change_difficulty(1)
        elif choice == "How to Play":
            self.state = "how"
        elif choice == "Credits":
            self.state = "credits"
        elif choice == "About":
            self.state = "about"
        elif choice == "Exit":
            self.running = False

    def _handle_match_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.sfx.play_menu_move()
            self.paused = False
            self.state = "menu"
            return
        if key == pygame.K_p:
            self.paused = not self.paused
            self.sfx.play_pause()
            return
        if key == pygame.K_r:
            self.sfx.play_menu_move()
            self.reset_match(play_sound=False)
            return
        if key == pygame.K_TAB:
            self.change_difficulty(1)

    def _handle_winner_key(self, key: int) -> None:
        if key in (pygame.K_y, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.sfx.play_menu_move()
            self.start_game()
        elif key in (pygame.K_n, pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.sfx.play_menu_move()
            self.state = "menu"

    def run(self) -> int:
        while self.running:
            dt = min(self.clock.tick(TARGET_FPS) / 1000.0, MAX_FRAME_DT)
            self.handle_events()
            self.update(dt)
            self.draw()

            if self.smoke_test:
                self.smoke_frames_remaining -= 1
                if self.smoke_frames_remaining <= 0:
                    self.running = False

        pygame.quit()
        return 0

    def update(self, dt: float) -> None:
        self.update_background(dt)
        self.update_particles(dt)

        self.player.flash = max(0.0, self.player.flash - dt * 3.2)
        self.ai.flash = max(0.0, self.ai.flash - dt * 3.2)
        self.ball.glow = max(0.0, self.ball.glow - dt * 3.5)
        self.score_flash_timer = max(0.0, self.score_flash_timer - dt * 2.2)
        self.point_text_timer = max(0.0, self.point_text_timer - dt)
        self.screen_shake_timer = max(0.0, self.screen_shake_timer - dt)
        if self.screen_shake_timer <= 0.0:
            self.screen_shake_strength = 0.0

        if self.state == "match" and not self.paused:
            self.update_match(dt)

    def update_background(self, dt: float) -> None:
        for star in self.stars:
            star.y += star.speed * dt
            if star.y > HEIGHT + 4:
                star.y = -4
                star.x = random.uniform(0, WIDTH)

    def update_particles(self, dt: float) -> None:
        alive: list[Particle] = []
        for particle in self.particles:
            particle.life -= dt
            if particle.life <= 0.0:
                continue
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vx *= 0.985
            particle.vy *= 0.985
            alive.append(particle)
        self.particles = alive

    def update_match(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        player_dir = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            player_dir -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            player_dir += 1.0

        self.player.velocity = player_dir * self.player.speed
        self.player.y += self.player.velocity * dt
        self.player.y = clamp(self.player.y, 0.0, HEIGHT - self.player.h)

        if self.serve_timer > 0.0:
            self.serve_timer = max(0.0, self.serve_timer - dt)
            self.ai_target_y = HEIGHT / 2 - self.ai.h / 2
            self.update_ai(dt)
            return

        self.update_ai(dt)
        self.advance_ball(dt)

    def update_ai(self, dt: float) -> None:
        difficulty = self.difficulty
        self.ai.speed = difficulty.ai_speed
        self.ai_think_timer -= dt

        if self.ai_think_timer <= 0.0:
            self.ai_think_timer = difficulty.ai_reaction
            predicted = self.predict_ball_y()
            noise = random.uniform(-difficulty.ai_error, difficulty.ai_error)
            self.ai_target_y = clamp(predicted - self.ai.h / 2 + noise, 0.0, HEIGHT - self.ai.h)

        deadzone = difficulty.ai_deadzone
        if self.ai.center_y < self.ai_target_y + self.ai.h / 2 - deadzone:
            self.ai.velocity = self.ai.speed
        elif self.ai.center_y > self.ai_target_y + self.ai.h / 2 + deadzone:
            self.ai.velocity = -self.ai.speed
        else:
            self.ai.velocity = 0.0

        self.ai.y += self.ai.velocity * dt
        self.ai.y = clamp(self.ai.y, 0.0, HEIGHT - self.ai.h)

    def predict_ball_y(self) -> float:
        if self.ball.vx < 0:
            return HEIGHT / 2

        x = self.ball.x
        y = self.ball.y
        vx = self.ball.vx
        vy = self.ball.vy
        target_x = self.ai.x - self.ball.size

        for _ in range(600):
            if x >= target_x:
                return y + self.ball.size / 2

            step = 1 / 240
            x += vx * step
            y += vy * step

            if y <= 0.0:
                y = 0.0
                vy *= -1
            elif y >= HEIGHT - self.ball.size:
                y = HEIGHT - self.ball.size
                vy *= -1

        return HEIGHT / 2

    def advance_ball(self, dt: float) -> None:
        distance = max(abs(self.ball.vx), abs(self.ball.vy)) * dt
        steps = max(1, int(distance // 6) + 1)
        step_dt = dt / steps

        for _ in range(steps):
            self.ball.x += self.ball.vx * step_dt
            self.ball.y += self.ball.vy * step_dt
            self.ball.trail.append(TrailNode(self.ball.x, self.ball.y, self.ball.size, 0.18))
            if len(self.ball.trail) > 18:
                self.ball.trail.pop(0)

            for node in self.ball.trail:
                node.life -= step_dt
            self.ball.trail = [node for node in self.ball.trail if node.life > 0.0]

            if self.ball.y <= 0.0:
                self.ball.y = 0.0
                self.ball.vy *= -1
                self.ball.glow = 1.0
                self.shake(2.0, 0.10)
                self.spawn_particles(self.ball.x + self.ball.size / 2, self.ball.y + 2, color=CYAN, count=6, base_speed=140.0)
                self.sfx.play_wall_hit()
            elif self.ball.y >= HEIGHT - self.ball.size:
                self.ball.y = HEIGHT - self.ball.size
                self.ball.vy *= -1
                self.ball.glow = 1.0
                self.shake(2.0, 0.10)
                self.spawn_particles(self.ball.x + self.ball.size / 2, self.ball.y + self.ball.size - 2, color=CYAN, count=6, base_speed=140.0)
                self.sfx.play_wall_hit()

            if self.check_paddle_collision():
                continue

            if self.ball.x + self.ball.size < 0.0:
                self.ai_score += 1
                self.point_text = "AI SCORES"
                self.point_text_timer = 0.85
                self.score_flash_timer = 1.0
                self.spawn_particles(WIDTH / 2, HEIGHT / 2, color=RED, count=18, base_speed=180.0)
                self.shake(7.0, 0.22)
                self.reset_round(direction=-1, play_sound=True)
                if self.ai_score >= WINNING_SCORE:
                    self.finish_match(player_won=False)
                return
            if self.ball.x > WIDTH:
                self.player_score += 1
                self.point_text = "PLAYER SCORES"
                self.point_text_timer = 0.85
                self.score_flash_timer = 1.0
                self.spawn_particles(WIDTH / 2, HEIGHT / 2, color=GREEN, count=18, base_speed=180.0)
                self.shake(7.0, 0.22)
                self.reset_round(direction=1, play_sound=True)
                if self.player_score >= WINNING_SCORE:
                    self.finish_match(player_won=True)
                return

    def check_paddle_collision(self) -> bool:
        ball_rect = self.ball.rect
        player_rect = self.player.rect
        ai_rect = self.ai.rect

        if ball_rect.colliderect(player_rect) and self.ball.vx < 0.0:
            self.ball.x = player_rect.right
            self.reflect_from_paddle(self.player, direction=1)
            return True

        if ball_rect.colliderect(ai_rect) and self.ball.vx > 0.0:
            self.ball.x = ai_rect.left - self.ball.size
            self.reflect_from_paddle(self.ai, direction=-1)
            return True

        return False

    def reflect_from_paddle(self, paddle: Paddle, *, direction: int) -> None:
        relative = clamp((self.ball.center_y - paddle.y) / paddle.h, 0.0, 0.999999)
        segment = int(relative * 8)
        vertical_table = [-330.0, -250.0, -180.0, -95.0, 95.0, 180.0, 250.0, 330.0]
        new_vx_mag = clamp(abs(self.ball.vx) * HIT_ACCELERATION, MIN_BALL_SPEED_X, MAX_BALL_SPEED_X)
        new_vy = vertical_table[segment]

        new_vy += paddle.velocity * 0.18
        new_vy = clamp(new_vy, -440.0, 440.0)

        self.ball.vx = new_vx_mag * direction
        self.ball.vy = new_vy
        self.ball.glow = 1.0
        paddle.flash = 1.0
        self.spawn_particles(
            self.ball.x + self.ball.size / 2,
            self.ball.y + self.ball.size / 2,
            color=WHITE,
            count=10,
            base_speed=200.0,
        )
        self.shake(3.0, 0.10)
        self.sfx.play_paddle_hit(abs(self.ball.vx))

    def finish_match(self, *, player_won: bool) -> None:
        self.paused = False
        self.state = "winner"
        self.winner_text = "YOU WIN!" if player_won else "AI WINS!"
        self.winner_color = GREEN if player_won else RED
        self.sfx.play_win()

    def draw(self) -> None:
        self.canvas.fill(BLACK)
        self.draw_background(self.canvas)

        if self.state == "menu":
            self.draw_menu(self.canvas)
        elif self.state == "how":
            self.draw_info_screen(
                self.canvas,
                "HOW TO PLAY",
                [
                    ("Move with W / S or Arrow Keys", WHITE, self.small_font),
                    ("Hit paddle edges to throw sharp angles", WHITE, self.small_font),
                    ("P = Pause   R = Restart   F11 = Fullscreen", WHITE, self.small_font),
                    ("TAB cycles difficulty during a match", GRAY, self.tiny_font),
                    ("ESC returns to the menu", GRAY, self.tiny_font),
                ],
            )
        elif self.state == "credits":
            self.draw_info_screen(
                self.canvas,
                "CREDITS",
                [
                    ("Single-file Python + Pygame arcade remake", WHITE, self.small_font),
                    ("Retro bounce logic with modern polish", WHITE, self.small_font),
                    ("Procedural sound, particles, trail, and shake", GRAY, self.tiny_font),
                    ("ESC to return", GRAY, self.tiny_font),
                ],
            )
        elif self.state == "about":
            self.draw_info_screen(
                self.canvas,
                "ABOUT",
                [
                    ("Classic Pong energy with smoother timing", WHITE, self.small_font),
                    ("Sub-step collisions prevent fast-ball tunneling", WHITE, self.small_font),
                    ("Designed to run cleanly on modern Python builds", GRAY, self.tiny_font),
                    ("ESC to return", GRAY, self.tiny_font),
                ],
            )
        else:
            self.draw_match(self.canvas)
            if self.state == "winner":
                self.draw_winner_overlay(self.canvas)
            elif self.paused:
                self.draw_pause_overlay(self.canvas)

        self.draw_scanlines(self.canvas)
        self.present_canvas()

    def present_canvas(self) -> None:
        offset_x = 0
        offset_y = 0
        if self.screen_shake_timer > 0.0 and self.screen_shake_strength > 0.0:
            offset_x = int(random.uniform(-self.screen_shake_strength, self.screen_shake_strength))
            offset_y = int(random.uniform(-self.screen_shake_strength, self.screen_shake_strength))

        self.screen.fill(BLACK)
        self.screen.blit(self.canvas, (offset_x, offset_y))
        pygame.display.flip()

    def draw_background(self, surface: pygame.Surface) -> None:
        surface.fill(DARK)
        for star in self.stars:
            color = (70 + star.size * 60, 80 + star.size * 60, 90 + star.size * 70)
            pygame.draw.rect(surface, color, (int(star.x), int(star.y), star.size, star.size))

        for y in range(0, HEIGHT, 32):
            pygame.draw.line(surface, (18, 24, 30), (0, y), (WIDTH, y), 1)

    def draw_text_center(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        x: int,
        y: int,
    ) -> None:
        text_surface = font.render(text, True, color)
        rect = text_surface.get_rect(center=(x, y))
        surface.blit(text_surface, rect)

    def draw_menu(self, surface: pygame.Surface) -> None:
        self.draw_text_center(surface, "AC'S Pong 0.1 infdev", self.title_font, WHITE, WIDTH // 2, 150)

        for index, label in enumerate(MENU_ITEMS):
            y = 280 + index * 52
            selected = index == self.menu_index
            color = GREEN if selected else WHITE

            if label == "Difficulty":
                text = f"Difficulty: {self.difficulty.name}"
            else:
                text = label

            if selected:
                pulse = 8 * math.sin(pygame.time.get_ticks() / 180)
                pygame.draw.rect(surface, (18, 60, 42), (WIDTH // 2 - 230, y - 24, 460, 40), border_radius=8)
                self.draw_text_center(surface, text, self.menu_font, color, WIDTH // 2 + int(pulse), y)
            else:
                self.draw_text_center(surface, text, self.menu_font, color, WIDTH // 2, y)

        self.draw_text_center(
            surface,
            "files. = off   import python3.14   UP / DOWN = Select   ENTER = Confirm",
            self.tiny_font,
            GRAY,
            WIDTH // 2,
            HEIGHT - 52,
        )

    def draw_info_screen(
        self,
        surface: pygame.Surface,
        heading: str,
        lines: list[tuple[str, tuple[int, int, int], pygame.font.Font]],
    ) -> None:
        self.draw_text_center(surface, heading, self.title_font, WHITE, WIDTH // 2, 128)
        start_y = 250
        for index, (text, color, font) in enumerate(lines):
            self.draw_text_center(surface, text, font, color, WIDTH // 2, start_y + index * 52)

    def draw_match(self, surface: pygame.Surface) -> None:
        self.draw_center_divider(surface)
        self.draw_scores(surface)
        self.draw_paddles(surface)
        self.draw_ball(surface)
        self.draw_particles(surface)

        self.draw_text_center(surface, "W / S or Arrows", self.tiny_font, GRAY, 112, HEIGHT - 28)
        self.draw_text_center(
            surface,
            f"{self.difficulty.name}  •  P Pause  •  R Restart  •  ESC Menu",
            self.tiny_font,
            GRAY,
            WIDTH // 2,
            HEIGHT - 28,
        )

        if self.serve_timer > 0.0:
            ready = "READY" if self.serve_timer > 0.45 else "GO"
            color = GOLD if ready == "READY" else GREEN
            self.draw_text_center(surface, ready, self.menu_font, color, WIDTH // 2, HEIGHT // 2 - 60)

        if self.point_text_timer > 0.0:
            self.draw_text_center(surface, self.point_text, self.small_font, WHITE, WIDTH // 2, 108)

    def draw_center_divider(self, surface: pygame.Surface) -> None:
        for y in range(0, HEIGHT, 28):
            pygame.draw.rect(surface, WHITE, (WIDTH // 2 - 2, y + 6, 4, 14))

    def draw_scores(self, surface: pygame.Surface) -> None:
        pulse = 1.0 + 0.08 * self.score_flash_timer
        player_font = self.huge_font if pulse > 1.01 else self.title_font
        ai_font = self.huge_font if pulse > 1.01 else self.title_font
        self.draw_text_center(surface, str(self.player_score), player_font, WHITE, WIDTH // 4, 74)
        self.draw_text_center(surface, str(self.ai_score), ai_font, WHITE, WIDTH * 3 // 4, 74)

    def draw_paddles(self, surface: pygame.Surface) -> None:
        for paddle, accent in ((self.player, GREEN), (self.ai, CYAN)):
            rect = paddle.rect
            pygame.draw.rect(surface, accent if paddle.flash > 0.0 else WHITE, rect, border_radius=2)
            if paddle.flash > 0.0:
                glow_rect = rect.inflate(8, 8)
                alpha = int(110 * paddle.flash)
                pygame.draw.rect(self.overlay, (*accent, alpha), glow_rect, border_radius=5)
                surface.blit(self.overlay, (0, 0))
                self.overlay.fill((0, 0, 0, 0))

    def draw_ball(self, surface: pygame.Surface) -> None:
        for node in self.ball.trail:
            alpha = int(140 * clamp(node.life / 0.18, 0.0, 1.0))
            size = max(4, int(node.size * 0.8))
            rect = pygame.Rect(int(node.x), int(node.y), size, size)
            pygame.draw.rect(self.overlay, (255, 255, 255, alpha), rect)
        surface.blit(self.overlay, (0, 0))
        self.overlay.fill((0, 0, 0, 0))

        ball_rect = self.ball.rect
        if self.ball.glow > 0.0:
            glow_rect = ball_rect.inflate(18, 18)
            alpha = int(120 * self.ball.glow)
            pygame.draw.rect(self.overlay, (255, 255, 255, alpha), glow_rect, border_radius=6)
            surface.blit(self.overlay, (0, 0))
            self.overlay.fill((0, 0, 0, 0))

        pygame.draw.rect(surface, WHITE, ball_rect, border_radius=2)

    def draw_particles(self, surface: pygame.Surface) -> None:
        for particle in self.particles:
            alpha = int(255 * clamp(particle.life / 0.45, 0.0, 1.0))
            pygame.draw.circle(
                self.overlay,
                (*particle.color, alpha),
                (int(particle.x), int(particle.y)),
                max(1, int(particle.size)),
            )
        surface.blit(self.overlay, (0, 0))
        self.overlay.fill((0, 0, 0, 0))

    def draw_pause_overlay(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (0, 0, 0), (120, 180, WIDTH - 240, 180), border_radius=12)
        pygame.draw.rect(surface, MID, (120, 180, WIDTH - 240, 180), 2, border_radius=12)
        self.draw_text_center(surface, "PAUSED", self.title_font, WHITE, WIDTH // 2, 248)
        self.draw_text_center(surface, "Press P to resume", self.small_font, GREEN, WIDTH // 2, 320)
        self.draw_text_center(surface, "ESC returns to menu", self.tiny_font, GRAY, WIDTH // 2, 366)

    def draw_winner_overlay(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (0, 0, 0), (90, 132, WIDTH - 180, 250), border_radius=14)
        pygame.draw.rect(surface, MID, (90, 132, WIDTH - 180, 250), 2, border_radius=14)
        self.draw_text_center(surface, self.winner_text, self.title_font, self.winner_color, WIDTH // 2, 205)
        self.draw_text_center(surface, f"{self.player_score}  -  {self.ai_score}", self.menu_font, WHITE, WIDTH // 2, 272)
        self.draw_text_center(surface, "ENTER / Y = Restart", self.small_font, WHITE, WIDTH // 2, 328)
        self.draw_text_center(surface, "N or ESC = Menu", self.tiny_font, GRAY, WIDTH // 2, 374)

    def draw_scanlines(self, surface: pygame.Surface) -> None:
        for y in range(0, HEIGHT, 4):
            pygame.draw.line(surface, (0, 0, 0), (0, y), (WIDTH, y), 1)

    def smoke_summary(self) -> str:
        return (
            f"smoke_test=ok difficulty={self.difficulty.name} "
            f"scores={self.player_score}-{self.ai_score} state={self.state}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AC'S Pong 0.1 infdev")
    parser.add_argument("--mute", action="store_true", help="disable synthesized sound effects")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="run a few frames and exit (useful for CI/headless checks)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    game = Game(mute=args.mute, smoke_test=args.smoke_test)
    exit_code = game.run()

    if args.smoke_test:
        print(game.smoke_summary())

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
