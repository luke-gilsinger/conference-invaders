import pygame
import sys
import os
import random
import json
from datetime import datetime
import controller

# --- CONFIG ---
WIDTH, HEIGHT = 1280, 800
FPS = 60
GAME_DURATION = 120  # seconds (2 minutes total cap)
LOGO_IMAGE_PATH = "logo.png"       # Branding
INTRO_IMAGE_PATH = "intro.png"     # Intro / title screen image (optional)
PLAYER_IMAGE_PATH = "player.png"   # Custom player image (optional)
ENEMY_IMAGES_DIR = "enemies"       # Directory containing up to 5 custom enemy PNGs
ENEMY_SIZE = (64, 48)
START_FULLSCREEN = False
LEADERBOARD_FILE = "leaderboard.json"
LEADERBOARD_MAX_ENTRIES = 50
INTRO_TOP_N = 8

# Difficulty tuning per level
INVADER_BASE_SPEED = 3
INVADER_SPEED_GROWTH = 0.6
ENEMY_FIRE_BASE = 90
ENEMY_FIRE_DECAY = 7
ENEMY_FIRE_MIN = 25
ENEMY_BULLET_BASE_SPEED = 7
ENEMY_BULLET_SPEED_GROWTH = 1.5
DESCENT_STEP = 24

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GRAY = (180, 180, 180)

pygame.init()
pygame.font.init()
font = pygame.font.SysFont("Arial", 28)
small_font = pygame.font.SysFont("Arial", 22)
mono_font = pygame.font.SysFont("Consolas", 22)

controller.init()

# --- Helpers ---
flags = 0

# Keep raw/original images so we can re-scale on fullscreen toggle
logo_raw = None
intro_image_raw = None

def create_screen(fullscreen=False):
    global WIDTH, HEIGHT, flags
    # Use SCALED + DOUBLEBUF for smoother mode switches and initial paint
    if fullscreen:
        flags = pygame.FULLSCREEN | pygame.SCALED | pygame.DOUBLEBUF
        info = pygame.display.Info()
        WIDTH, HEIGHT = info.current_w, info.current_h
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    else:
        flags = pygame.SCALED | pygame.DOUBLEBUF
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption("Conference Invaders")
    # Immediate flip helps avoid a first-frame black screen on some platforms
    pygame.display.flip()
    return screen


def rescale_assets():
    """Re-scale images to current WIDTH/HEIGHT after mode change."""
    global logo, intro_image
    # Scale logo
    if logo_raw:
        max_logo_w = max(150, WIDTH // 6)
        ratio = logo_raw.get_width() / max(1, logo_raw.get_height())
        w = min(max_logo_w, logo_raw.get_width())
        h = int(w / max(1, ratio))
        logo = pygame.transform.smoothscale(logo_raw, (w, h))
    else:
        logo = None
    # Scale intro image
    if intro_image_raw:
        iw, ih = intro_image_raw.get_size()
        scale = min(WIDTH / iw * 0.9, HEIGHT / ih * 0.75)
        intro_w, intro_h = int(iw * scale), int(ih * scale)
        intro_w = max(1, intro_w); intro_h = max(1, intro_h)
        intro_image = pygame.transform.smoothscale(intro_image_raw, (intro_w, intro_h))
    else:
        intro_image = None


# Parse CLI args
is_fullscreen = START_FULLSCREEN or ("--fullscreen" in sys.argv)
if "--windowed" in sys.argv:
    is_fullscreen = False

screen = create_screen(is_fullscreen)
clock = pygame.time.Clock()

# --- Load Images ---
logo = None
if os.path.exists(LOGO_IMAGE_PATH):
    logo_raw = pygame.image.load(LOGO_IMAGE_PATH).convert_alpha()

intro_image = None
if os.path.exists(INTRO_IMAGE_PATH):
    intro_image_raw = pygame.image.load(INTRO_IMAGE_PATH).convert_alpha()

# Initial scale to current display size
rescale_assets()

player_image = None
if os.path.exists(PLAYER_IMAGE_PATH):
    player_image = pygame.image.load(PLAYER_IMAGE_PATH).convert_alpha()
    player_image = pygame.transform.smoothscale(player_image, (80, 60))

enemy_images = []
if os.path.exists(ENEMY_IMAGES_DIR):
    for file in os.listdir(ENEMY_IMAGES_DIR):
        if file.lower().endswith(".png"):
            img = pygame.image.load(os.path.join(ENEMY_IMAGES_DIR, file)).convert_alpha()
            img = pygame.transform.smoothscale(img, ENEMY_SIZE)
            enemy_images.append(img)
        if len(enemy_images) >= 5:
            break
if not enemy_images:
    fallback = pygame.Surface(ENEMY_SIZE, pygame.SRCALPHA)
    fallback.fill(RED)
    enemy_images = [fallback]

# --- Leaderboard persistence & export ---
def load_leaderboard():
    try:
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []

def save_leaderboard(entries):
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

leaderboard = load_leaderboard()

def export_leaderboard_csv(csv_path: str = "leaderboard.csv") -> bool:
    """Export leaderboard to CSV. Returns True on success."""
    try:
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Company", "Score", "Level", "Timestamp"]) 
            for e in leaderboard:
                writer.writerow([
                    e.get("name", ""),
                    e.get("company", ""),
                    e.get("score", 0),
                    e.get("level", 0),
                    e.get("ts", "")
                ])
        return True
    except Exception:
        return False

def add_score(name, company, score, level):
    """Add a score entry. Name/company are optional (may be empty strings)."""
    global leaderboard
    entry = {
        "name": (name or "")[:16],
        "company": (company or "")[:18],
        "score": int(score),
        "level": int(level),
        "ts": datetime.now().isoformat(timespec="seconds")
    }
    leaderboard.append(entry)
    leaderboard.sort(key=lambda e: (e.get("score", 0), e.get("level", 0)), reverse=True)
    leaderboard = leaderboard[:LEADERBOARD_MAX_ENTRIES]
    save_leaderboard(leaderboard)

# --- Sprites ---
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        if player_image:
            self.image = player_image.copy()
        else:
            self.image = pygame.Surface((70, 40))
            self.image.fill((0, 255, 0))
        self.rect = self.image.get_rect(midbottom=(WIDTH // 2, HEIGHT - 30))
        self.speed = 8
    def reset(self):
        self.rect.midbottom = (WIDTH // 2, HEIGHT - 30)
    def update(self, keys):
        if keys[pygame.K_LEFT] and self.rect.left > 0:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT] and self.rect.right < WIDTH:
            self.rect.x += self.speed
        
        if controller.controller.axes[2].x == -1 and self.rect.left > 0:
            self.rect.x -= self.speed
        if controller.controller.axes[2].x == 1 and self.rect.right < WIDTH:
            self.rect.x += self.speed

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, color=WHITE, speed=-10, size=(6, 20)):
        super().__init__()
        self.image = pygame.Surface(size)
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = speed
    def update(self):
        self.rect.y += self.speed
        if self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()

class Invader(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = random.choice(enemy_images)
        self.rect = self.image.get_rect(topleft=(x, y))

# --- Groups ---
player = Player()
player_group = pygame.sprite.GroupSingle(player)
bullets = pygame.sprite.Group()
invaders = pygame.sprite.Group()
enemy_bullets = pygame.sprite.Group()

# --- Wave / Level generation ---
def spawn_wave(level:int):
    invaders.empty()
    base_rows = 5
    rows = min(base_rows + (level - 1) // 2, 8)
    cols = 10
    cell_w = ENEMY_SIZE[0] + 24
    start_x = max(40, (WIDTH - cols * cell_w) // 2)
    start_y = 80
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * cell_w
            y = start_y + r * (ENEMY_SIZE[1] + 28)
            invaders.add(Invader(x, y))

# --- Variables ---
level = 1
invader_dx = INVADER_BASE_SPEED
score = 0
start_ticks = None

# --- Leaderboard render helpers ---
def draw_leaderboard(surface, entries, title="Top Scores", top_n=10, x=None, y=None):
    if x is None: x = WIDTH // 2
    if y is None: y = int(HEIGHT * 0.62)
    header = font.render(title, True, WHITE)
    surface.blit(header, (x - header.get_width() // 2, y))
    y += header.get_height() + 6
    shown = entries[:top_n]
    if not shown:
        msg = small_font.render("No scores yet. Be the first!", True, GRAY)
        surface.blit(msg, (x - msg.get_width() // 2, y))
        return

    # column headers
    hdr = mono_font.render(f"   NAME              COMPANY            SCORE  LVL", True, GRAY)
    surface.blit(hdr, (x - 320, y))
    y += hdr.get_height() + 2

    for idx, e in enumerate(shown, start=1):
        name = e.get('name') or '—'
        company = e.get('company') or '—'
        line = f"{idx:>2}. {name:<16}  {company:<18}  {e['score']:>5}  L{e['level']:<2}"
        txt = mono_font.render(line, True, WHITE)
        surface.blit(txt, (x - 320, y))
        y += txt.get_height() + 2

# --- Settings (hidden) ---

def confirm_clear_leaderboard():
    """Ask the admin to type CONFIRM to clear the leaderboard."""
    global leaderboard
    msg = small_font.render("Type 'CONFIRM' then Enter to clear, or Esc to cancel", True, WHITE)
    typed = ""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_RETURN:
                    if typed.strip().upper() == "CONFIRM":
                        leaderboard = []
                        save_leaderboard(leaderboard)
                        screen.fill(BLACK)
                        ok = small_font.render("Leaderboard cleared.", True, WHITE)
                        screen.blit(ok, (WIDTH//2 - ok.get_width()//2, HEIGHT//2))
                        pygame.display.flip()
                        pygame.time.wait(1000)
                        return True
                elif event.key == pygame.K_BACKSPACE:
                    typed = typed[:-1]
                elif event.unicode and event.unicode.isprintable():
                    typed += event.unicode
        screen.fill(BLACK)
        title = font.render("Settings", True, WHITE)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 80))
        screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 30))
        box = mono_font.render(typed, True, WHITE)
        pygame.draw.rect(screen, (60,60,60), (WIDTH//2-200, HEIGHT//2+10, 400, 40), border_radius=6)
        screen.blit(box, (WIDTH//2 - 190, HEIGHT//2 + 16))
        pygame.display.flip()
        clock.tick(FPS)


def show_settings():
    """Hidden settings page. Access from Intro with the S key."""
    info_msg = ""
    info_timer = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_i:
                    return
                if event.key == pygame.K_c:
                    if confirm_clear_leaderboard():
                        info_msg = "Leaderboard cleared."
                        info_timer = pygame.time.get_ticks() + 2000
                if event.key == pygame.K_e:
                    ok = export_leaderboard_csv()
                    info_msg = "Exported to leaderboard.csv" if ok else "Export failed."
                    info_timer = pygame.time.get_ticks() + 2500
                if event.key == pygame.K_F11:
                    toggle_fullscreen()
        screen.fill(BLACK)
        title = font.render("Settings", True, WHITE)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 120))
        hint = small_font.render("Press 'C' to Clear Leaderboard (requires confirmation)", True, WHITE)
        export_hint = small_font.render("Press 'E' to Export Leaderboard to CSV", True, WHITE)
        back = small_font.render("Press Esc or I to go back", True, GRAY)
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, 200))
        screen.blit(export_hint, (WIDTH//2 - export_hint.get_width()//2, 232))
        screen.blit(back, (WIDTH//2 - back.get_width()//2, 264))
        draw_leaderboard(screen, leaderboard, title="Top Scores (preview)", top_n=5, x=WIDTH//2, y=320)
        # transient info message
        if info_msg and pygame.time.get_ticks() < info_timer:
            msg_surface = small_font.render(info_msg, True, WHITE)
            pygame.draw.rect(screen, (40,40,40), (WIDTH//2-220, HEIGHT-100, 440, 40), border_radius=8)
            screen.blit(msg_surface, (WIDTH//2 - msg_surface.get_width()//2, HEIGHT - 92))
        pygame.display.flip()
        clock.tick(FPS)

# --- Intro Screen ---

def draw_intro_frame():
    screen.fill(BLACK)
    # Draw logo centered top if available
    y_offset = 40
    if logo:
        lr = logo.get_rect(midtop=(WIDTH // 2, y_offset))
        screen.blit(logo, lr)
        y_offset = lr.bottom + 20
    title = font.render("Conference Invaders", True, WHITE)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, y_offset))
    hint1 = small_font.render("Press Space to Start", True, WHITE)
    hint2 = small_font.render("F11: Toggle Fullscreen | Esc: Quit", True, WHITE)
    if intro_image:
        ir = intro_image.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.38)))
        screen.blit(intro_image, ir)
        y_after = ir.bottom + 20
    else:
        y_after = y_offset + 60
    screen.blit(hint1, (WIDTH // 2 - hint1.get_width() // 2, y_after))
    screen.blit(hint2, (WIDTH // 2 - hint2.get_width() // 2, y_after + 40))
    draw_leaderboard(screen, leaderboard, title="Top Scores", top_n=INTRO_TOP_N)
    pygame.display.flip()


def show_intro():
    draw_intro_frame()
    # Hidden: press 'S' to open Settings (not shown on screen)
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_SPACE:
                    waiting = False
                if event.key == pygame.K_s:
                    show_settings(); draw_intro_frame()
                if event.key == pygame.K_F11:
                    toggle_fullscreen()
                    draw_intro_frame()
                    pygame.display.flip()
        clock.tick(60)

# Fullscreen toggle

def toggle_fullscreen():
    global screen, is_fullscreen
    is_fullscreen = not is_fullscreen
    screen = create_screen(is_fullscreen)
    # Re-scale assets to the new resolution
    rescale_assets()
    # Give the display a moment to settle, then pump events
    for _ in range(3):
        pygame.event.pump()
        pygame.time.wait(10)
    # One immediate clear to ensure no stale buffer
    screen.fill(BLACK)
    pygame.display.flip()

# Level banner

def show_level_banner(level:int):
    banner = font.render(f"Level {level}", True, WHITE)
    timer = 0
    while timer < 900:  # ~0.9 seconds
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                toggle_fullscreen()
        screen.fill(BLACK)
        if logo:
            screen.blit(logo, (WIDTH - logo.get_width() - 16, 16))
        screen.blit(banner, (WIDTH//2 - banner.get_width()//2, HEIGHT//2 - banner.get_height()//2))
        pygame.display.flip()
        clock.tick(FPS)
        timer += 1000 // FPS

# Name + Company input at Game Over (both optional)

def text_input_screen(title_text: str, placeholder: str = "", max_chars: int = 16):
    typed = ""
    caret_visible = True
    caret_timer = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return typed.strip()
                if event.key == pygame.K_ESCAPE:
                    return ""
                if event.key == pygame.K_BACKSPACE:
                    typed = typed[:-1]
                elif len(typed) < max_chars and event.unicode.isprintable():
                    typed += event.unicode
        # Blink caret
        caret_timer = (caret_timer + clock.get_time()) % 1000
        caret_visible = caret_timer < 600
        screen.fill(BLACK)
        if logo:
            screen.blit(logo, (WIDTH - logo.get_width() - 16, 16))
        title = font.render(title_text, True, WHITE)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 20))
        # Input box
        typed_surface = mono_font.render(typed or placeholder, True, WHITE if typed else GRAY)
        box_w = max(380, typed_surface.get_width() + 24)
        box_rect = pygame.Rect(WIDTH // 2 - box_w // 2, HEIGHT // 2 + 30, box_w, 44)
        pygame.draw.rect(screen, (60,60,60), box_rect, border_radius=6)
        pygame.draw.rect(screen, (140,140,140), box_rect, 2, border_radius=6)
        screen.blit(typed_surface, (box_rect.x + 12, box_rect.y + 9))
        if caret_visible and typed:
            cx = box_rect.x + 12 + typed_surface.get_width() + 2
            cy = box_rect.y + 9
            pygame.draw.rect(screen, WHITE, (cx, cy, 2, 26))
        pygame.display.flip()
        clock.tick(FPS)

# --- Main Game Session ---

def run_game():
    global start_ticks, invader_dx, score, level, enemy_bullets
    # Reset for a fresh session
    level = 1
    score = 0

    enemy_bullets = pygame.sprite.Group()

    # Initialize first wave
    spawn_wave(level)
    invader_dx = INVADER_BASE_SPEED
    player.reset()

    start_ticks = pygame.time.get_ticks()
    running = True
    while running:
        clock.tick(FPS)
        keys = pygame.key.get_pressed()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    bullets.add(Bullet(player.rect.centerx, player.rect.top))
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_F11:
                    toggle_fullscreen()

        # Update
        player_group.update(keys)
        bullets.update(); enemy_bullets.update()

        # Move invaders as a block
        move_down = False
        for invader in invaders:
            invader.rect.x += invader_dx
            if invader.rect.right >= WIDTH - 10 or invader.rect.left <= 10:
                move_down = True
        if move_down:
            invader_dx *= -1
            for invader in invaders:
                invader.rect.y += DESCENT_STEP

        # Random enemy fire (scales with level)
        fire_n = max(ENEMY_FIRE_MIN, ENEMY_FIRE_BASE - ENEMY_FIRE_DECAY * (level - 1))
        if invaders and random.randint(1, fire_n) == 1:
            shooter = random.choice(invaders.sprites())
            speed = ENEMY_BULLET_BASE_SPEED + ENEMY_BULLET_SPEED_GROWTH * (level - 1)
            enemy_bullets.add(Bullet(shooter.rect.centerx, shooter.rect.bottom, RED, speed, size=(6, 18)))

        # Collisions
        for bullet in bullets:
            hit = pygame.sprite.spritecollideany(bullet, invaders)
            if hit:
                bullet.kill(); hit.kill(); score += 10
        if pygame.sprite.spritecollideany(player, enemy_bullets):
            running = False

        # Level cleared -> next level (respect time cap)
        elapsed = (pygame.time.get_ticks() - start_ticks) / 1000
        remaining = max(0, GAME_DURATION - int(elapsed))
        if not invaders and remaining > 0:
            level += 1
            invader_dx = int(INVADER_BASE_SPEED + (level - 1) * INVADER_SPEED_GROWTH)
            bullets.empty(); enemy_bullets.empty()
            player.reset()
            spawn_wave(level)
            show_level_banner(level)

        # Draw
        screen.fill(BLACK)
        player_group.draw(screen)
        bullets.draw(screen)
        invaders.draw(screen)
        enemy_bullets.draw(screen)
        if logo:
            screen.blit(logo, (WIDTH - logo.get_width() - 16, 16))

        # HUD
        timer_text = small_font.render(f"Time: {remaining}", True, WHITE)
        score_text = small_font.render(f"Score: {score}", True, WHITE)
        lvl_text = small_font.render(f"Level: {level}", True, WHITE)
        base_y = 16 + (logo.get_height() + 8 if logo else 0)
        screen.blit(timer_text, (16, base_y))
        screen.blit(score_text, (16, base_y + 28))
        screen.blit(lvl_text, (16, base_y + 56))

        # End conditions
        if remaining <= 0:
            running = False

        pygame.display.flip()

    # Game Over -> Inputs -> Save -> Final leaderboard screen
    name = text_input_screen("Enter your Name", "Name", 16)
    company = text_input_screen("Enter your Company", "Company", 18)
    add_score(name, company, score, level)

    screen.fill(BLACK)
    over_text = font.render("Thanks for Playing!", True, WHITE)
    details = small_font.render(
        f"Saved: {name or '—'} | {company or '—'} | Score: {score} | Level: {level}", True, WHITE
    )
    screen.blit(over_text, (WIDTH // 2 - over_text.get_width() // 2, HEIGHT // 2 - 120))
    screen.blit(details, (WIDTH // 2 - details.get_width() // 2, HEIGHT // 2 - 80))
    draw_leaderboard(screen, leaderboard, title="Leaderboard", top_n=12, x=WIDTH//2, y=HEIGHT//2 - 20)
    pygame.display.flip()

# --- Post-Game Menu / Replay ---

def post_game_menu():
    """Show replay/quit options. Returns 'intro' or 'quit'."""
    KIOSK_AUTO_RESTART = False
    KIOSK_DELAY = 3
    if KIOSK_AUTO_RESTART:
        end_time = pygame.time.get_ticks() + KIOSK_DELAY * 1000
        while pygame.time.get_ticks() < end_time:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 'quit'
            remaining = max(0, (end_time - pygame.time.get_ticks()) // 1000)
            overlay = small_font.render(f"Restarting in {remaining}s... (Press R to replay, ESC to quit)", True, WHITE)
            screen.blit(overlay, (WIDTH//2 - overlay.get_width()//2, HEIGHT - 60))
            pygame.display.flip()
            clock.tick(FPS)
        return 'intro'

    prompt1 = small_font.render("Press R to Replay", True, WHITE)
    prompt2 = small_font.render("Press I for Intro, ESC to Quit", True, WHITE)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return 'quit'
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    return 'quit'
                if event.key in (pygame.K_r, pygame.K_i, pygame.K_SPACE):
                    return 'intro'
                if event.key == pygame.K_F11:
                    toggle_fullscreen()
        pygame.draw.rect(screen, (0,0,0), (0, HEIGHT-90, WIDTH, 90))
        screen.blit(prompt1, (WIDTH//2 - prompt1.get_width()//2, HEIGHT - 84))
        screen.blit(prompt2, (WIDTH//2 - prompt2.get_width()//2, HEIGHT - 52))
        pygame.display.flip()
        clock.tick(FPS)

# --- Flow ---
while True:
    show_intro()
    run_game()
    action = post_game_menu()
    if action == 'quit':
        break

pygame.quit()
