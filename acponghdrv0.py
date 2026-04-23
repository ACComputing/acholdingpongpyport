import math
import random
import array
import pygame

pygame.init()
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
    AUDIO_OK = True
except pygame.error:
    AUDIO_OK = False

WIDTH, HEIGHT = 800, 600
FPS = 60
ATARI_SPEED = 0.72

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AC'S Pong")

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 70, 70)
GRAY = (110, 110, 110)

title_font = pygame.font.SysFont("Arial", 96, bold=True)
menu_font = pygame.font.SysFont("Arial", 44)
small_font = pygame.font.SysFont("Arial", 30)
tiny_font = pygame.font.SysFont("Arial", 22)

menu_options = ["Play Game", "How to Play", "Credits", "About", "Exit"]
selected = 0


def draw_text(text, font, color, surface, x, y):
    textobj = font.render(text, True, color)
    textrect = textobj.get_rect(center=(x, y))
    surface.blit(textobj, textrect)


def clamp(value, low, high):
    return max(low, min(high, value))


def make_tone(freq=440, duration_ms=80, volume=0.35, wave_type="square", decay=True):
    if not AUDIO_OK:
        return None

    sample_rate = 22050
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = array.array("h")

    for i in range(n_samples):
        t = i / sample_rate
        env = 1.0
        if decay:
            env = max(0.0, 1.0 - (i / max(1, n_samples - 1)))

        if wave_type == "square":
            sample = 1.0 if math.sin(2.0 * math.pi * freq * t) >= 0 else -1.0
        elif wave_type == "triangle":
            sample = (2.0 / math.pi) * math.asin(math.sin(2.0 * math.pi * freq * t))
        else:
            sample = math.sin(2.0 * math.pi * freq * t)

        val = int(32767 * volume * env * sample)
        buf.append(val)

    return pygame.mixer.Sound(buffer=buf.tobytes())


class DynamicSoundEngine:
    def __init__(self):
        self.enabled = AUDIO_OK
        if not self.enabled:
            self.paddle_low = None
            self.paddle_high = None
            self.wall = None
            self.score = None
            self.menu = None
            self.win = None
            return

        self.paddle_low = make_tone(220, 55, 0.34, "square")
        self.paddle_high = make_tone(420, 45, 0.30, "square")
        self.wall = make_tone(160, 40, 0.22, "triangle")
        self.score = make_tone(110, 140, 0.38, "square")
        self.menu = make_tone(520, 35, 0.18, "square")
        self.win = make_tone(660, 180, 0.25, "triangle")

    def play(self, sound):
        if self.enabled and sound is not None:
            sound.play()

    def play_menu_move(self):
        self.play(self.menu)

    def play_paddle_hit(self, speed_mag):
        if not self.enabled:
            return
        if speed_mag < 7.5:
            self.play(self.paddle_low)
        else:
            self.play(self.paddle_high)

    def play_wall_hit(self):
        self.play(self.wall)

    def play_score(self):
        self.play(self.score)

    def play_win(self):
        self.play(self.win)


sfx = DynamicSoundEngine()


def main_menu():
    global selected
    clock = pygame.time.Clock()

    while True:
        screen.fill(BLACK)
        draw_text("AC'S Pong", title_font, WHITE, screen, WIDTH // 2, 150)
        draw_text(
            "60 FPS  •  Atari speed  •  authentic Pong physics",
            tiny_font,
            GRAY,
            screen,
            WIDTH // 2,
            215,
        )

        for i, option in enumerate(menu_options):
            color = GREEN if i == selected else WHITE
            draw_text(option, menu_font, color, screen, WIDTH // 2, 290 + i * 62)

        draw_text("UP / DOWN to move   ENTER to select", tiny_font, GRAY, screen, WIDTH // 2, HEIGHT - 52)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(menu_options)
                    sfx.play_menu_move()
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(menu_options)
                    sfx.play_menu_move()
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    sfx.play_menu_move()
                    choice = menu_options[selected]
                    if choice == "Play Game":
                        play_game()
                    elif choice == "How to Play":
                        show_how_to_play()
                    elif choice == "Credits":
                        show_credits()
                    elif choice == "About":
                        show_about()
                    elif choice == "Exit":
                        pygame.quit()
                        raise SystemExit

        pygame.display.flip()
        clock.tick(FPS)


def pong_segment_bounce(paddle_y, paddle_h, ball_y, ball_h, incoming_speed_x):
    """
    Classic Pong-style segmented bounce:
    paddle is split into 8 horizontal bands.
    Top bands send the ball upward, bottom bands downward.
    Center bands are nearly horizontal.
    """
    center_y = ball_y + ball_h / 2
    relative = (center_y - paddle_y) / paddle_h
    relative = clamp(relative, 0.0, 0.999999)

    segment = int(relative * 8)

    vertical_table = [-5, -4, -3, -2, 2, 3, 4, 5]
    new_vy = vertical_table[segment] * ATARI_SPEED
    new_vx_mag = max(5.5 * ATARI_SPEED, abs(incoming_speed_x))

    return new_vx_mag, new_vy


def play_game():
    paddle_w, paddle_h = 14, 96
    ball_size = 14

    player_y = HEIGHT // 2 - paddle_h // 2
    ai_y = HEIGHT // 2 - paddle_h // 2

    base_ball_speed_x = 6.5 * ATARI_SPEED
    player_speed = 8.0 * ATARI_SPEED
    ai_speed = 5.7 * ATARI_SPEED

    ball_x = WIDTH // 2 - ball_size // 2
    ball_y = HEIGHT // 2 - ball_size // 2
    ball_speed_x = random.choice([-base_ball_speed_x, base_ball_speed_x])
    ball_speed_y = random.choice([-3, 3]) * ATARI_SPEED

    player_score = 0
    ai_score = 0
    winning_score = 5

    clock = pygame.time.Clock()

    def reset_ball(direction=None):
        nonlocal ball_x, ball_y, ball_speed_x, ball_speed_y
        ball_x = WIDTH // 2 - ball_size // 2
        ball_y = HEIGHT // 2 - ball_size // 2

        if direction is None:
            direction = random.choice([-1, 1])

        ball_speed_x = base_ball_speed_x * direction
        ball_speed_y = random.choice([-3, 3]) * ATARI_SPEED

    while True:
        screen.fill(BLACK)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            player_y -= player_speed
        if keys[pygame.K_s]:
            player_y += player_speed

        ai_center = ai_y + paddle_h / 2
        ball_center = ball_y + ball_size / 2
        if ai_center < ball_center - 8:
            ai_y += ai_speed
        elif ai_center > ball_center + 8:
            ai_y -= ai_speed

        player_y = clamp(player_y, 0, HEIGHT - paddle_h)
        ai_y = clamp(ai_y, 0, HEIGHT - paddle_h)

        ball_x += ball_speed_x
        ball_y += ball_speed_y

        if ball_y <= 0:
            ball_y = 0
            ball_speed_y *= -1
            sfx.play_wall_hit()
        elif ball_y >= HEIGHT - ball_size:
            ball_y = HEIGHT - ball_size
            ball_speed_y *= -1
            sfx.play_wall_hit()

        player_rect = pygame.Rect(28, int(player_y), paddle_w, paddle_h)
        ai_rect = pygame.Rect(WIDTH - 28 - paddle_w, int(ai_y), paddle_w, paddle_h)
        ball_rect = pygame.Rect(int(ball_x), int(ball_y), ball_size, ball_size)

        if ball_rect.colliderect(player_rect) and ball_speed_x < 0:
            ball_x = player_rect.right
            new_vx, new_vy = pong_segment_bounce(player_y, paddle_h, ball_y, ball_size, ball_speed_x)
            ball_speed_x = new_vx
            ball_speed_y = new_vy
            sfx.play_paddle_hit(abs(ball_speed_x))

        elif ball_rect.colliderect(ai_rect) and ball_speed_x > 0:
            ball_x = ai_rect.left - ball_size
            new_vx, new_vy = pong_segment_bounce(ai_y, paddle_h, ball_y, ball_size, ball_speed_x)
            ball_speed_x = -new_vx
            ball_speed_y = new_vy
            sfx.play_paddle_hit(abs(ball_speed_x))

        if ball_x + ball_size < 0:
            ai_score += 1
            sfx.play_score()
            reset_ball(direction=-1)
        elif ball_x > WIDTH:
            player_score += 1
            sfx.play_score()
            reset_ball(direction=1)

        pygame.draw.rect(screen, WHITE, player_rect)
        pygame.draw.rect(screen, WHITE, ai_rect)
        pygame.draw.rect(screen, WHITE, ball_rect)

        for y in range(0, HEIGHT, 28):
            pygame.draw.rect(screen, WHITE, (WIDTH // 2 - 2, y + 6, 4, 14))

        draw_text(str(player_score), small_font, WHITE, screen, WIDTH // 4, 42)
        draw_text(str(ai_score), small_font, WHITE, screen, WIDTH * 3 // 4, 42)
        draw_text("W / S", tiny_font, GRAY, screen, 80, HEIGHT - 28)
        draw_text("ESC = Menu", tiny_font, GRAY, screen, WIDTH - 95, HEIGHT - 28)

        pygame.display.flip()
        clock.tick(FPS)

        if player_score >= winning_score or ai_score >= winning_score:
            sfx.play_win()
            winner_text = "YOU WIN!" if player_score >= winning_score else "AI WINS!"
            winner_color = GREEN if player_score >= winning_score else RED

            while True:
                screen.fill(BLACK)
                draw_text(winner_text, title_font, winner_color, screen, WIDTH // 2, 180)
                draw_text(f"{player_score}  -  {ai_score}", small_font, WHITE, screen, WIDTH // 2, 270)
                draw_text("Y = Restart", small_font, WHITE, screen, WIDTH // 2, 355)
                draw_text("N or ESC = Menu", tiny_font, GRAY, screen, WIDTH // 2, 405)

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        raise SystemExit
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_y:
                            sfx.play_menu_move()
                            return play_game()
                        if event.key in (pygame.K_n, pygame.K_ESCAPE):
                            sfx.play_menu_move()
                            return

                pygame.display.flip()
                clock.tick(FPS)


def show_how_to_play():
    clock = pygame.time.Clock()
    running = True
    while running:
        screen.fill(BLACK)
        draw_text("HOW TO PLAY", title_font, WHITE, screen, WIDTH // 2, 120)
        draw_text("Left paddle: W / S", small_font, WHITE, screen, WIDTH // 2, 250)
        draw_text("Hit top or bottom paddle zones to angle the ball", small_font, WHITE, screen, WIDTH // 2, 302)
        draw_text("Middle hits stay flatter, like classic Pong", tiny_font, GRAY, screen, WIDTH // 2, 354)
        draw_text("ESC to return", tiny_font, GRAY, screen, WIDTH // 2, 440)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                sfx.play_menu_move()

        pygame.display.flip()
        clock.tick(FPS)


def show_credits():
    clock = pygame.time.Clock()
    running = True
    while running:
        screen.fill(BLACK)
        draw_text("CREDITS", title_font, WHITE, screen, WIDTH // 2, 145)
        draw_text("Single-file Python + Pygame Pong", small_font, WHITE, screen, WIDTH // 2, 280)
        draw_text("Authentic segmented Pong paddle bounce", small_font, WHITE, screen, WIDTH // 2, 328)
        draw_text("ESC to return", tiny_font, GRAY, screen, WIDTH // 2, 430)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                sfx.play_menu_move()

        pygame.display.flip()
        clock.tick(FPS)


def show_about():
    clock = pygame.time.Clock()
    running = True
    while running:
        screen.fill(BLACK)
        draw_text("ABOUT", title_font, WHITE, screen, WIDTH // 2, 145)
        draw_text("AC'S Pong tuned for classic arcade-style rebounds", small_font, WHITE, screen, WIDTH // 2, 280)
        draw_text("8 paddle bands control the ball angle", tiny_font, GRAY, screen, WIDTH // 2, 330)
        draw_text("ESC to return", tiny_font, GRAY, screen, WIDTH // 2, 430)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                sfx.play_menu_move()

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main_menu()
