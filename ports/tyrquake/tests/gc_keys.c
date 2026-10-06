/*
 * Harness for tyrquake patch 0002: compiles the PATCHED common/in_sdl.c against the
 * build image's SDL headers, fakes a pad with every button and both triggers pressed,
 * runs IN_Commands and checks that every key reaching Key_Event is a real key
 * (K_GCA..K_LAST-1), that the buttons and the two triggers each arrive exactly once,
 * and that an out-of-range button is dropped by the key table guard.
 */
#include "in_sdl.c"   /* the patched source, from $SRC */

#include <stdio.h>

static int seen[512];
static int nevents, bad;

void Key_Event(knum_t key, qboolean down)
{
    nevents++;
    if ((int)key < K_GCA || (int)key >= K_LAST) {
        printf("BAD key %d (K_GCA %d, K_LAST %d)\n", (int)key, K_GCA, K_LAST);
        bad++;
        return;
    }
    if (down)
        seen[key]++;
}

static int pressed_buttons;
static int pressed_triggers;

Uint8 SDL_GameControllerGetButton(SDL_GameController *c, SDL_GameControllerButton b)
{
    (void)c; (void)b;
    return pressed_buttons;
}

Sint16 SDL_GameControllerGetAxis(SDL_GameController *c, SDL_GameControllerAxis a)
{
    (void)c; (void)a;
    return pressed_triggers ? 32767 : 0;
}

static void setup_pad(void)
{
    gamecontroller_available = true;
}

int main(void)
{
    int k, fails = 0;

    printf("SDL_CONTROLLER_BUTTON_MAX = %d, K_GCA = %d, K_GCRIGHT = %d, K_GCLEFTTRIGGER = %d, "
           "K_GCRIGHTTRIGGER = %d, K_LAST = %d\n",
           (int)SDL_CONTROLLER_BUTTON_MAX, (int)K_GCA, (int)K_GCRIGHT, (int)K_GCLEFTTRIGGER,
           (int)K_GCRIGHTTRIGGER, (int)K_LAST);

    setup_pad();
    pressed_buttons = 1;
    pressed_triggers = 1;
    IN_Commands();

    for (k = K_GCA; k < K_LAST; k++)
        if (seen[k] != 1) {
            printf("key %d seen %d times (want 1)\n", k, seen[k]);
            fails++;
        }
    if (bad) {
        printf("%d key(s) out of range reached Key_Event\n", bad);
        fails++;
    }
    if (nevents != K_LAST - K_GCA) {
        printf("events %d, want %d\n", nevents, K_LAST - K_GCA);
        fails++;
    }

    /* the guard itself: anything outside K_GCA..K_LAST-1 is dropped before Key_Event */
    nevents = 0;
    IN_GameControllerKey(K_LAST, true);
    IN_GameControllerKey(K_LAST + 4, true);
    IN_GameControllerKey(K_LAST + 5, false);
    IN_GameControllerKey(K_GCA - 1, true);
    IN_GameControllerKey(-1, true);
    if (nevents != 0) {
        printf("guard let %d out-of-range keys through\n", nevents);
        fails++;
    }

    /* release everything: every key goes up once */
    pressed_buttons = 0;
    pressed_triggers = 0;
    nevents = 0;
    IN_Commands();
    if (nevents != K_LAST - K_GCA) {
        printf("release events %d, want %d\n", nevents, K_LAST - K_GCA);
        fails++;
    }

    printf(fails ? "FAIL\n" : "PASS\n");
    return fails ? 1 : 0;
}
