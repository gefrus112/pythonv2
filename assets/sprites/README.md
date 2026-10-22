# Free sprites for PyHope games

Eight original, public-domain (CC0) pixel sprites. SVG keeps every edge crisp
at any size. The Games page animates them with reduced-motion-safe CSS, and
`examples/games/sprite_animation.pyv2` demonstrates reusable character states.
See `LICENSE.md`.

Use them in HTML:

```html
<img src="assets/sprites/comet-hero.svg" alt="Comet Kid">
```

Or load them in a Canvas game:

```js
const hero = new Image();
hero.src = "assets/sprites/comet-hero.svg";
```

The playable web demos also contain procedural fallbacks, so the games still
run if an image has not finished loading.
