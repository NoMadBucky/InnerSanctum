"""Opening shot, composed in the polished hourglass photograph's coordinates."""
import cv2
import numpy as np
from PIL import Image


class HourglassShot:
    def __init__(self, path, size):
        self.size = size
        with Image.open(path) as source:
            image = np.array(source.convert("RGB").resize((1024, 1024)))
        y, x = np.ogrid[:1024, :1024]
        red, green, blue = image.astype(int).transpose(2, 0, 1)
        # Remove photographed grains only in the air between throat and pile.
        # Preserve glass reflections, the pinch, and the original mound.
        air = ((y > 520) & (y < 758 + .46*abs(x-512)) &
               (abs(x-512) < 9 + .48*(y-520)))
        grain = air & (red > green*1.13) & (green > blue*1.35) & (red > 67)
        mask = cv2.dilate(grain.astype("uint8"), np.ones((3, 3), "uint8"))
        self.plate = cv2.inpaint(image, mask, 4, cv2.INPAINT_TELEA)
        rng = np.random.default_rng(1903)
        self.grains = []
        for _ in range(290):
            # A narrow gravity-fed column, with a few grains thrown wider.
            drift = rng.normal(0, 10 if rng.random() < .90 else 34)
            color = tuple(int(c) for c in image[rng.integers(850, 875), rng.integers(445, 575)])
            self.grains.append((rng.random(), rng.uniform(.86, 1.18), drift,
                                rng.normal(0, 1.6), rng.uniform(.75, 2.25), color))
        h, w = size[1], size[0]
        v, u = np.mgrid[:h, :w]
        edge = ((u-w/2)/(w*.66))**2 + ((v-h*.49)/(h*.62))**2
        self.vignette = np.clip(1-.40*edge, .42, 1).astype("float32")[:, :, None]

    def frame(self, t, announce):
        photo = self.plate.copy()
        for phase, speed, drift, offset, radius, color in self.grains:
            u = (phase+t*speed) % 1
            x = 511 + offset + drift*u
            depth = .34*u + .66*u*u
            y = 518 + (240 + .46*abs(x-512))*depth
            # Fractional coordinates and a short vertical streak at terminal speed.
            cv2.ellipse(photo, (round(x*16), round(y*16)),
                        (round(radius*16), round(radius*(1 + .55*u)*16)),
                        0, 0, 360, color, -1, cv2.LINE_AA, shift=4)

        # A slow macro push during the credit. Pull focus and dolly back on
        # the title cue; the hourglass stays continuous behind the typography.
        u = np.clip((t-announce)/1.12, 0, 1)
        ease = u*u*(3-2*u)
        scale = (1.53 + .07*min(t/announce, 1))*(1-ease) + .91*ease
        transform = np.array([[scale, 0, 320-512*scale],
                              [0, scale, 355+94*ease-517*scale]])
        shot = cv2.warpAffine(photo, transform, self.size, flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
        if ease > .01:
            shot = cv2.GaussianBlur(shot, (0, 0), .1+2.3*ease)
        shot = shot*self.vignette*(.96-.52*ease)
        return Image.fromarray(shot.astype("uint8")).convert("RGBA")
