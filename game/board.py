import random
import math
import pygame

GRID_SIZE = 8
TILE_SIZE = 60

GEM_COLORS = [
    (220, 50, 50),    # Red
    (50, 200, 50),    # Green
    (50, 100, 240),   # Blue
    (240, 200, 40),   # Yellow
    (180, 50, 220),   # Purple
    (240, 130, 40),   # Orange
]


class Gem:

    def __init__(self, color, target_row, col, special=None):
        self.color = color
        self.target_row = target_row
        self.col = col

        # None = normal gem
        # "row" = clears entire row
        # "column" = clears entire column
        self.special = special

        self.current_y = (target_row - 2) * TILE_SIZE
        self.target_y = target_row * TILE_SIZE
        self.fall_speed = 12.0

    def update(self):
        if self.current_y < self.target_y:
            self.current_y += self.fall_speed

            if self.current_y > self.target_y:
                self.current_y = self.target_y

    def is_animating(self):
        return self.current_y < self.target_y


class Board:

    def __init__(
        self,
        offset_x,
        offset_y,
        target_score=500,
        max_moves=20
    ):
        self.offset_x = offset_x
        self.offset_y = offset_y

        self.target_score = target_score
        self.max_moves = max_moves

        self.grid = [
            [None for _ in range(GRID_SIZE)]
            for _ in range(GRID_SIZE)
        ]

        self.selected = None

        self.score = 0
        self.moves_remaining = max_moves

        # Cascade information
        self.last_combo = 0

        # Hint information
        self.hint_pair = None
        self.hint_phase = 0.0

        self.reset()

    # ---------------------------------------------------------
    # RESET
    # ---------------------------------------------------------

    def reset(self):
        self.score = 0
        self.moves_remaining = self.max_moves
        self.selected = None

        self.last_combo = 0
        self.hint_pair = None
        self.hint_phase = 0.0

        # Create the initial board.
        #
        # We avoid creating immediate matches so that the player
        # starts with a clean board.
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):

                available_colors = GEM_COLORS[:]

                # Prevent horizontal 3-match
                if c >= 2:
                    available_colors = [
                        color
                        for color in available_colors
                        if not (
                            self.grid[r][c - 1]
                            and self.grid[r][c - 2]
                            and self.grid[r][c - 1].color == color
                            and self.grid[r][c - 2].color == color
                        )
                    ]

                # Prevent vertical 3-match
                if r >= 2:
                    available_colors = [
                        color
                        for color in available_colors
                        if not (
                            self.grid[r - 1][c]
                            and self.grid[r - 2][c]
                            and self.grid[r - 1][c].color == color
                            and self.grid[r - 2][c].color == color
                        )
                    ]

                color = random.choice(
                    available_colors or GEM_COLORS
                )

                gem = Gem(color, r, c)

                # Initial board should appear immediately.
                gem.current_y = gem.target_y

                self.grid[r][c] = gem

        # Safety check.
        self.resolve_matches(score_matches=False)

    # ---------------------------------------------------------
    # ANIMATION
    # ---------------------------------------------------------

    def is_animating(self):
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):

                gem = self.grid[r][c]

                if gem and gem.is_animating():
                    return True

        return False

    # ---------------------------------------------------------
    # SWAPPING
    # ---------------------------------------------------------

    def swap_gems(self, pos1, pos2):

        r1, c1 = pos1
        r2, c2 = pos2

        self.grid[r1][c1], self.grid[r2][c2] = (
            self.grid[r2][c2],
            self.grid[r1][c1]
        )

        # Update positions of the swapped gems.
        for r, c in (pos1, pos2):

            gem = self.grid[r][c]

            if gem:
                gem.target_row = r
                gem.col = c
                gem.target_y = r * TILE_SIZE
                gem.current_y = r * TILE_SIZE

    def is_adjacent(self, pos1, pos2):

        r1, c1 = pos1
        r2, c2 = pos2

        return abs(r1 - r2) + abs(c1 - c2) == 1

    # ---------------------------------------------------------
    # MATCH DETECTION
    # ---------------------------------------------------------

    def find_matches(self):

        matched = set()

        # -------------------------
        # Horizontal matches
        # -------------------------

        for r in range(GRID_SIZE):

            c = 0

            while c < GRID_SIZE:

                gem = self.grid[r][c]

                if gem is None:
                    c += 1
                    continue

                end = c + 1

                while (
                    end < GRID_SIZE
                    and self.grid[r][end]
                    and self.grid[r][end].color == gem.color
                ):
                    end += 1

                run_length = end - c

                if run_length >= 3:

                    for col in range(c, end):
                        matched.add((r, col))

                c = end

        # -------------------------
        # Vertical matches
        # -------------------------

        for c in range(GRID_SIZE):

            r = 0

            while r < GRID_SIZE:

                gem = self.grid[r][c]

                if gem is None:
                    r += 1
                    continue

                end = r + 1

                while (
                    end < GRID_SIZE
                    and self.grid[end][c]
                    and self.grid[end][c].color == gem.color
                ):
                    end += 1

                run_length = end - r

                if run_length >= 3:

                    for row in range(r, end):
                        matched.add((row, c))

                r = end

        return matched

    # ---------------------------------------------------------
    # FIND 4-IN-A-ROW SPECIAL
    # ---------------------------------------------------------

    def find_special_creation(
        self,
        matches,
        preferred_pos=None
    ):
        """
        Finds a horizontal or vertical group of 4+ gems.

        Returns:

        (
            position_to_keep,
            "row" or "column",
            cells_in_group
        )

        """

        # -------------------------
        # Horizontal 4+
        # -------------------------

        for r in range(GRID_SIZE):

            c = 0

            while c < GRID_SIZE:

                gem = self.grid[r][c]

                if gem is None:
                    c += 1
                    continue

                end = c + 1

                while (
                    end < GRID_SIZE
                    and self.grid[r][end]
                    and self.grid[r][end].color == gem.color
                ):
                    end += 1

                if end - c >= 4:

                    cells = {
                        (r, col)
                        for col in range(c, end)
                    }

                    # Prefer the gem that was moved by the player.
                    if preferred_pos in cells:
                        keep_position = preferred_pos
                    else:
                        keep_position = (
                            r,
                            c + (end - c) // 2
                        )

                    return (
                        keep_position,
                        "row",
                        cells
                    )

                c = end

        # -------------------------
        # Vertical 4+
        # -------------------------

        for c in range(GRID_SIZE):

            r = 0

            while r < GRID_SIZE:

                gem = self.grid[r][c]

                if gem is None:
                    r += 1
                    continue

                end = r + 1

                while (
                    end < GRID_SIZE
                    and self.grid[end][c]
                    and self.grid[end][c].color == gem.color
                ):
                    end += 1

                if end - r >= 4:

                    cells = {
                        (row, c)
                        for row in range(r, end)
                    }

                    if preferred_pos in cells:
                        keep_position = preferred_pos
                    else:
                        keep_position = (
                            r + (end - r) // 2,
                            c
                        )

                    return (
                        keep_position,
                        "column",
                        cells
                    )

                r = end

        return None

    # ---------------------------------------------------------
    # DROP AND REFILL
    # ---------------------------------------------------------

    def drop_and_refill(self):

        # IMPORTANT:
        # This outer loop fixes the original "c is not defined"
        # runtime error.
        for c in range(GRID_SIZE):

            empty_slots = 0

            # Start from the bottom of the column.
            for r in range(GRID_SIZE - 1, -1, -1):

                if self.grid[r][c] is None:

                    empty_slots += 1

                elif empty_slots > 0:

                    gem = self.grid[r][c]

                    new_row = r + empty_slots

                    gem.target_row = new_row
                    gem.col = c
                    gem.target_y = new_row * TILE_SIZE

                    self.grid[new_row][c] = gem

                    self.grid[r][c] = None

            # Create new gems at the top.
            for r in range(empty_slots):

                color = random.choice(GEM_COLORS)

                gem = Gem(
                    color,
                    r,
                    c
                )

                gem.current_y = -(
                    (empty_slots - r) * TILE_SIZE
                )

                gem.target_y = r * TILE_SIZE

                self.grid[r][c] = gem

    # ---------------------------------------------------------
    # SPECIAL GEM ACTIVATION
    # ---------------------------------------------------------

    def expand_special_matches(self, matches):

        expanded = set(matches)

        for r, c in list(matches):

            gem = self.grid[r][c]

            if gem is None:
                continue

            # Special row-clearing gem
            if gem.special == "row":

                for col in range(GRID_SIZE):
                    expanded.add((r, col))

            # Special column-clearing gem
            elif gem.special == "column":

                for row in range(GRID_SIZE):
                    expanded.add((row, c))

        return expanded

    # ---------------------------------------------------------
    # MATCH RESOLUTION + CASCADE
    # ---------------------------------------------------------

    def resolve_matches(
        self,
        initial_matches=None,
        preferred_pos=None,
        score_matches=True
    ):

        total_cleared = 0
        combo = 0

        if initial_matches is None:
            matches = self.find_matches()
        else:
            matches = initial_matches

        while matches:

            combo += 1

            # Check whether a 4+ match should create a special gem.
            special_creation = self.find_special_creation(
                matches,
                preferred_pos
            )

            keep_position = None
            special_type = None

            if special_creation:

                (
                    keep_position,
                    special_type,
                    _
                ) = special_creation

            # Expand existing special gems.
            expanded_matches = self.expand_special_matches(
                matches
            )

            # Don't immediately activate the newly created special.
            if keep_position in expanded_matches:
                expanded_matches.remove(
                    keep_position
                )

            cleared_this_wave = len(
                expanded_matches
            )

            # Remove matched gems.
            for r, c in expanded_matches:
                self.grid[r][c] = None

            # Turn one of the matched gems into the special gem.
            if keep_position is not None:

                r, c = keep_position

                gem = self.grid[r][c]

                if gem:

                    gem.special = special_type
                    gem.target_row = r
                    gem.col = c

            total_cleared += cleared_this_wave

            # -------------------------------------------------
            # TASK 2
            # Cascade multiplier
            #
            # First wave  = 1x
            # Second wave = 2x
            # Third wave  = 3x
            # -------------------------------------------------

            if score_matches:

                multiplier = combo

                self.score += (
                    cleared_this_wave
                    * 10
                    * multiplier
                )

            # Gravity and refill.
            self.drop_and_refill()

            # Look for the next cascade.
            matches = self.find_matches()

            # Only the initial swap gets the preference.
            preferred_pos = None

        if score_matches:
            self.last_combo = combo
        else:
            self.last_combo = 0

        return total_cleared

    # ---------------------------------------------------------
    # PROCESS PLAYER SWAP
    # ---------------------------------------------------------

    def process_swap(self, pos1, pos2):

        if (
            not self.is_adjacent(pos1, pos2)
            or self.is_game_over()
            or self.is_animating()
        ):
            return False

        # Remove the idle hint.
        self.hint_pair = None

        # Perform swap.
        self.swap_gems(pos1, pos2)

        # Check whether swap produces a match.
        matches = self.find_matches()

        # -----------------------------------------------------
        # TASK 1
        #
        # IMPORTANT:
        # The move is NOT deducted yet.
        #
        # If there is no match, revert the swap and return.
        # -----------------------------------------------------

        if not matches:

            self.swap_gems(pos1, pos2)

            return False

        # Valid swap!
        # Now and only now consume one move.
        self.moves_remaining -= 1

        # Resolve matches and cascades.
        self.resolve_matches(
            initial_matches=matches,
            preferred_pos=pos2,
            score_matches=True
        )

        return True

    # ---------------------------------------------------------
    # TASK 4 - FIND VALID HINT
    # ---------------------------------------------------------

    def find_hint(self):

        if self.is_animating():
            return None

        # Check every horizontal and vertical adjacent pair.
        for r in range(GRID_SIZE):

            for c in range(GRID_SIZE):

                # Right neighbour
                if c + 1 < GRID_SIZE:

                    pair = (
                        (r, c),
                        (r, c + 1)
                    )

                    self.swap_gems(*pair)

                    valid = bool(
                        self.find_matches()
                    )

                    self.swap_gems(*pair)

                    if valid:
                        return pair

                # Bottom neighbour
                if r + 1 < GRID_SIZE:

                    pair = (
                        (r, c),
                        (r + 1, c)
                    )

                    self.swap_gems(*pair)

                    valid = bool(
                        self.find_matches()
                    )

                    self.swap_gems(*pair)

                    if valid:
                        return pair

        return None

    # ---------------------------------------------------------
    # GAME OVER
    # ---------------------------------------------------------

    def is_game_over(self):

        return (
            self.score >= self.target_score
            or self.moves_remaining <= 0
        )

    # ---------------------------------------------------------
    # RESULT
    # ---------------------------------------------------------

    def check_result(self):

        if self.score >= self.target_score:
            return "WIN"

        if self.moves_remaining <= 0:
            return "LOSS"

        return None

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    def update(self):

        for r in range(GRID_SIZE):

            for c in range(GRID_SIZE):

                gem = self.grid[r][c]

                if gem:
                    gem.update()

        # Used for the pulsing hint animation.
        self.hint_phase += 0.12

    # ---------------------------------------------------------
    # RENDER
    # ---------------------------------------------------------

    def render(self, surface):

        board_rect = pygame.Rect(
            self.offset_x,
            self.offset_y,
            GRID_SIZE * TILE_SIZE,
            GRID_SIZE * TILE_SIZE
        )

        pygame.draw.rect(
            surface,
            (20, 22, 28),
            board_rect,
            border_radius=8
        )

        pygame.draw.rect(
            surface,
            (60, 65, 75),
            board_rect,
            width=3,
            border_radius=8
        )

        # -----------------------------------------------------
        # TASK 4
        # Pulsing hint indicator
        # -----------------------------------------------------

        if self.hint_pair:

            pulse = (
                pygame.time.get_ticks() % 1000
            ) / 1000.0

            width = 2 + int(
                2 * (
                    0.5
                    + 0.5 * math.sin(
                        pulse * math.tau
                    )
                )
            )

            for r, c in self.hint_pair:

                x = (
                    self.offset_x
                    + c * TILE_SIZE
                )

                y = (
                    self.offset_y
                    + r * TILE_SIZE
                )

                hint_rect = pygame.Rect(
                    x + 2,
                    y + 2,
                    TILE_SIZE - 4,
                    TILE_SIZE - 4
                )

                pygame.draw.rect(
                    surface,
                    (255, 255, 255),
                    hint_rect,
                    width=width,
                    border_radius=10
                )

        # -----------------------------------------------------
        # DRAW GEMS
        # -----------------------------------------------------

        for r in range(GRID_SIZE):

            for c in range(GRID_SIZE):

                gem = self.grid[r][c]

                if gem is None:
                    continue

                x = (
                    self.offset_x
                    + c * TILE_SIZE
                )

                y = (
                    self.offset_y
                    + gem.current_y
                )

                tile_rect = pygame.Rect(
                    x + 2,
                    y + 2,
                    TILE_SIZE - 4,
                    TILE_SIZE - 4
                )

                pygame.draw.rect(
                    surface,
                    gem.color,
                    tile_rect,
                    border_radius=10
                )

                # -------------------------------------------------
                # TASK 3
                # Draw enhanced special gem
                # -------------------------------------------------

                if gem.special:

                    # Glowing white border
                    pygame.draw.rect(
                        surface,
                        (255, 255, 255),
                        tile_rect,
                        width=4,
                        border_radius=10
                    )

                    center_x, center_y = (
                        tile_rect.center
                    )

                    # Row-clearing symbol
                    if gem.special == "row":

                        pygame.draw.line(
                            surface,
                            (255, 255, 255),
                            (
                                tile_rect.left + 8,
                                center_y
                            ),
                            (
                                tile_rect.right - 8,
                                center_y
                            ),
                            4
                        )

                    # Column-clearing symbol
                    elif gem.special == "column":

                        pygame.draw.line(
                            surface,
                            (255, 255, 255),
                            (
                                center_x,
                                tile_rect.top + 8
                            ),
                            (
                                center_x,
                                tile_rect.bottom - 8
                            ),
                            4
                        )

                else:

                    pygame.draw.rect(
                        surface,
                        (255, 255, 255),
                        tile_rect,
                        width=1,
                        border_radius=10
                    )

                # -------------------------------------------------
                # SELECTED GEM
                # -------------------------------------------------

                if self.selected == (r, c):

                    pygame.draw.rect(
                        surface,
                        (255, 255, 255),
                        tile_rect,
                        width=4,
                        border_radius=10
                    )