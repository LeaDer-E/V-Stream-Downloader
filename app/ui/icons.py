import math
from typing import Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)

from app.theme import T


def logo_pixmap(size: int = 64, dpr: float = 2.0) -> QPixmap:
    px_size = int(size * dpr)
    pix = QPixmap(px_size, px_size)
    pix.fill(Qt.transparent)
    pix.setDevicePixelRatio(dpr)

    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

    s = float(size)
    pad = s * 0.055
    badge_rect = QRectF(pad, pad, s - pad * 2, s - pad * 2)
    radius = s * 0.24

    badge_path = QPainterPath()
    badge_path.addRoundedRect(badge_rect, radius, radius)

    p.save()
    p.setClipPath(badge_path)

    bg_grad = QLinearGradient(badge_rect.topLeft(), badge_rect.bottomRight())
    c_top = T.c("bg1", force_dark=True).lighter(125)
    c_bot = T.c("bg0", force_dark=True).darker(115)
    bg_grad.setColorAt(0.0, c_top)
    bg_grad.setColorAt(1.0, c_bot)
    p.fillPath(badge_path, bg_grad)

    glow = QRadialGradient(QPointF(s * 0.50, s * 0.52), s * 0.44)
    glow.setColorAt(0.0, T.c("accent", alpha=110, force_dark=True))
    glow.setColorAt(0.6, T.c("accent2", alpha=45, force_dark=True))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillPath(badge_path, glow)

    stroke_w = max(2.2, s * 0.125)
    p_left = QPointF(s * 0.245, s * 0.275)
    p_apex = QPointF(s * 0.500, s * 0.695)
    p_right = QPointF(s * 0.755, s * 0.275)

    p.setBrush(Qt.NoBrush)
    sh_off = s * 0.025
    sh_pen = QPen(QColor(0, 0, 0, 125), stroke_w * 1.12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(sh_pen)
    p.drawPolyline(
        QPolygonF(
            [
                QPointF(p_left.x(), p_left.y() + sh_off),
                QPointF(p_apex.x(), p_apex.y() + sh_off),
                QPointF(p_right.x(), p_right.y() + sh_off),
            ]
        )
    )

    grad_right = QLinearGradient(p_right, p_apex)
    grad_right.setColorAt(0.0, T.c("accent", force_dark=True).lighter(108))
    grad_right.setColorAt(1.0, T.c("accent2", force_dark=True).darker(135))
    pen_right = QPen(QBrush(grad_right), stroke_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen_right)
    p.drawLine(p_apex, p_right)

    cast_pen = QPen(QColor(5, 6, 15, 115), stroke_w * 1.06, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(cast_pen)
    p.drawLine(QPointF(s * 0.26, s * 0.29), QPointF(s * 0.512, s * 0.705))

    grad_left = QLinearGradient(p_left, p_apex)
    top_hi = T.c("accent_hi", force_dark=True).lighter(120)
    grad_left.setColorAt(0.0, top_hi)
    grad_left.setColorAt(0.55, T.c("accent", force_dark=True).lighter(110))
    grad_left.setColorAt(1.0, T.c("accent", force_dark=True))
    pen_left = QPen(QBrush(grad_left), stroke_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen_left)
    p.drawLine(p_left, p_apex)

    if size >= 24:
        play_poly = QPolygonF(
            [
                QPointF(s * 0.450, s * 0.255),
                QPointF(s * 0.570, s * 0.330),
                QPointF(s * 0.450, s * 0.405),
            ]
        )
        play_grad = QLinearGradient(QPointF(s * 0.45, s * 0.25), QPointF(s * 0.57, s * 0.41))
        play_grad.setColorAt(0.0, QColor("#FFFFFF"))
        play_grad.setColorAt(1.0, T.c("accent_hi", force_dark=True).lighter(125))
        p.setBrush(play_grad)
        p.setPen(QPen(QBrush(play_grad), max(1.2, s * 0.028), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolygon(play_poly)

    tray_w = max(1.5, s * 0.048)
    t_left = QPointF(s * 0.345, s * 0.775)
    t_mid = QPointF(s * 0.500, s * 0.855)
    t_right = QPointF(s * 0.655, s * 0.775)
    tray_grad = QLinearGradient(t_left, t_right)
    tray_grad.setColorAt(0.0, QColor("#FFFFFF"))
    tray_grad.setColorAt(0.5, T.c("accent_hi", force_dark=True).lighter(120))
    tray_grad.setColorAt(1.0, T.c("accent", force_dark=True).lighter(115))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QBrush(tray_grad), tray_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline(QPolygonF([t_left, t_mid, t_right]))

    rim_grad = QLinearGradient(badge_rect.topLeft(), badge_rect.bottomLeft())
    rim_grad.setColorAt(0.0, QColor(255, 255, 255, 135))
    rim_grad.setColorAt(0.5, T.c("border_hi", alpha=90, force_dark=True))
    rim_grad.setColorAt(1.0, T.c("accent", alpha=55, force_dark=True))
    rim_pen = QPen(QBrush(rim_grad), max(1.0, s * 0.022))
    p.setPen(rim_pen)
    p.setBrush(Qt.NoBrush)
    inset = max(0.6, s * 0.011)
    p.drawRoundedRect(badge_rect.adjusted(inset, inset, -inset, -inset), radius - inset, radius - inset)

    p.restore()
    p.end()
    return pix


def draw_icon(
    p: QPainter,
    name: str,
    rect: QRectF,
    color: Optional[QColor] = None,
    stroke_width: float = 1.95,
) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    col = QColor(color) if color is not None else T.c("text")

    duo_fill = QColor(col)
    duo_fill.setAlpha(max(28, min(68, int(col.alpha() * 0.24))))
    duo_mid = QColor(col)
    duo_mid.setAlpha(max(45, min(115, int(col.alpha() * 0.42))))

    scale_x = rect.width() / 24.0
    scale_y = rect.height() / 24.0
    scale = min(scale_x, scale_y)

    p.translate(
        rect.left() + (rect.width() - 24.0 * scale) / 2.0,
        rect.top() + (rect.height() - 24.0 * scale) / 2.0,
    )
    p.scale(scale, scale)

    pen = QPen(col, stroke_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    if name == "downloads":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(3.5, 14.5, 17.0, 5.5), 2.5, 2.5)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(12.0, 3.5), QPointF(12.0, 14.2))
        p.drawPolyline(QPolygonF([QPointF(7.8, 10.2), QPointF(12.0, 14.6), QPointF(16.2, 10.2)]))
        sub_pen = QPen(duo_mid, stroke_width * 0.85, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(sub_pen)
        p.drawPolyline(QPolygonF([QPointF(9.2, 6.2), QPointF(12.0, 9.0), QPointF(14.8, 6.2)]))

    elif name == "subtitles":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(2.8, 4.5, 18.4, 15.0), 3.8, 3.8)
        p.setBrush(duo_mid)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(5.5, 9.5, 7.5, 2.4), 1.2, 1.2)
        p.drawRoundedRect(QRectF(14.5, 9.5, 4.0, 2.4), 1.2, 1.2)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(5.5, 13.8, 4.5, 2.4), 1.2, 1.2)
        p.drawRoundedRect(QRectF(11.5, 13.8, 7.0, 2.4), 1.2, 1.2)

    elif name == "themes":
        p.save()
        p.translate(12.0, 18.5)
        p.rotate(24.0)
        p.setBrush(duo_fill)
        p.setPen(QPen(duo_mid, 1.5))
        p.drawRoundedRect(QRectF(-3.6, -13.5, 7.2, 13.5), 2.2, 2.2)
        p.restore()

        p.save()
        p.translate(10.0, 18.5)
        p.rotate(8.0)
        p.setBrush(duo_mid)
        p.setPen(QPen(col, 1.5))
        p.drawRoundedRect(QRectF(-3.6, -14.0, 7.2, 14.0), 2.2, 2.2)
        p.restore()

        p.setBrush(duo_fill)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(4.2, 4.2, 7.8, 15.2), 2.5, 2.5)
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(5.8, 6.0, 4.6, 4.2), 1.2, 1.2)
        p.drawEllipse(QPointF(8.1, 16.2), 1.2, 1.2)

        star = QPolygonF(
            [
                QPointF(18.5, 3.0),
                QPointF(19.3, 5.2),
                QPointF(21.5, 6.0),
                QPointF(19.3, 6.8),
                QPointF(18.5, 9.0),
                QPointF(17.7, 6.8),
                QPointF(15.5, 6.0),
                QPointF(17.7, 5.2),
            ]
        )
        p.setBrush(col)
        p.drawPolygon(star)

    elif name == "settings":
        p.setBrush(duo_fill)
        p.drawEllipse(QPointF(12.0, 12.0), 6.4, 6.4)
        for i in range(8):
            angle = i * (math.pi / 4.0)
            x1, y1 = 12.0 + math.cos(angle) * 6.2, 12.0 + math.sin(angle) * 6.2
            x2, y2 = 12.0 + math.cos(angle) * 9.0, 12.0 + math.sin(angle) * 9.0
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(12.0, 12.0), 2.5, 2.5)

    elif name == "about":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(3.2, 3.2, 17.6, 17.6), 6.0, 6.0)
        p.drawLine(QPointF(12.0, 11.0), QPointF(12.0, 16.5))
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(12.0, 7.6), 1.25, 1.25)

    elif name == "mail":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(3.0, 5.2, 18.0, 13.6), 3.0, 3.0)
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(4.2, 6.8), QPointF(12.0, 12.8), QPointF(19.8, 6.8)]))

    elif name == "phone":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(6.2, 2.8, 11.6, 18.4), 3.0, 3.0)
        p.drawLine(QPointF(10.0, 5.2), QPointF(14.0, 5.2))
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(12.0, 18.2), 1.15, 1.15)

    elif name == "heart":
        path = QPainterPath()
        path.moveTo(12.0, 19.5)
        path.cubicTo(4.0, 14.2, 3.2, 7.8, 7.5, 5.5)
        path.cubicTo(9.8, 4.4, 12.0, 6.2, 12.0, 7.8)
        path.cubicTo(12.0, 6.2, 14.2, 4.4, 16.5, 5.5)
        path.cubicTo(20.8, 7.8, 20.0, 14.2, 12.0, 19.5)
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawPath(path)

    elif name == "paste":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(3.5, 8.0, 9.2, 8.0), 4.0, 4.0)
        p.drawRoundedRect(QRectF(11.3, 8.0, 9.2, 8.0), 4.0, 4.0)
        p.drawLine(QPointF(9.0, 12.0), QPointF(15.0, 12.0))

    elif name == "bolt" or name == "bulb":
        poly = QPolygonF(
            [
                QPointF(13.2, 3.2),
                QPointF(5.8, 13.2),
                QPointF(11.5, 13.2),
                QPointF(10.4, 20.8),
                QPointF(18.2, 10.8),
                QPointF(12.5, 10.8),
            ]
        )
        p.setBrush(duo_mid)
        p.drawPolygon(poly)

    elif name == "search":
        p.setBrush(duo_fill)
        p.drawEllipse(QPointF(10.5, 10.5), 6.4, 6.4)
        p.drawLine(QPointF(15.2, 15.2), QPointF(20.2, 20.2))
        p.setPen(QPen(duo_mid, 1.4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(6.8, 6.8, 7.4, 7.4), 45 * 16, 85 * 16)

    elif name == "play":
        p.setBrush(col)
        p.setPen(QPen(col, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolygon(QPolygonF([QPointF(8.2, 5.8), QPointF(18.2, 12.0), QPointF(8.2, 18.2)]))

    elif name == "pause":
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(6.8, 5.5, 3.6, 13.0), 1.6, 1.6)
        p.drawRoundedRect(QRectF(13.6, 5.5, 3.6, 13.0), 1.6, 1.6)

    elif name == "stop":
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(6.8, 6.8, 10.4, 10.4), 2.6, 2.6)

    elif name == "close":
        p.drawLine(QPointF(7.0, 7.0), QPointF(17.0, 17.0))
        p.drawLine(QPointF(17.0, 7.0), QPointF(7.0, 17.0))

    elif name == "minimize":
        p.drawLine(QPointF(6.0, 12.0), QPointF(18.0, 12.0))

    elif name == "maximize":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(5.8, 5.8, 12.4, 12.4), 2.5, 2.5)

    elif name == "folder":
        back = QPainterPath()
        back.moveTo(3.2, 6.5)
        back.lineTo(9.2, 6.5)
        back.lineTo(11.4, 8.8)
        back.lineTo(20.8, 8.8)
        back.lineTo(20.8, 18.8)
        back.lineTo(3.2, 18.8)
        back.closeSubpath()
        p.setBrush(duo_fill)
        p.drawPath(back)
        p.setBrush(duo_mid)
        p.drawRoundedRect(QRectF(3.2, 10.2, 17.6, 8.6), 2.2, 2.2)

    elif name == "link" or name == "copy":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(4.5, 4.5, 11.0, 11.0), 2.6, 2.6)
        p.setBrush(T.c("surface"))
        p.drawRoundedRect(QRectF(8.5, 8.5, 11.0, 11.0), 2.6, 2.6)
        p.setBrush(duo_mid)
        p.drawRoundedRect(QRectF(8.5, 8.5, 11.0, 11.0), 2.6, 2.6)

    elif name == "check":
        p.setBrush(duo_fill)
        p.drawEllipse(QPointF(12.0, 12.0), 9.0, 9.0)
        p.setBrush(Qt.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(7.5, 12.2), QPointF(10.8, 15.5), QPointF(16.8, 8.8)]))

    elif name == "playlist":
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(3.5, 5.5, 12.5, 2.4), 1.2, 1.2)
        p.drawRoundedRect(QRectF(3.5, 10.5, 12.5, 2.4), 1.2, 1.2)
        p.setBrush(duo_mid)
        p.drawRoundedRect(QRectF(3.5, 15.5, 8.5, 2.4), 1.2, 1.2)
        p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(14.8, 13.5), QPointF(20.5, 16.8), QPointF(14.8, 20.0)]))

    elif name == "channel" or name == "youtube" or name == "video":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(3.0, 5.2, 18.0, 13.6), 4.0, 4.0)
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(9.8, 8.8), QPointF(15.8, 12.0), QPointF(9.8, 15.2)]))

    elif name == "audio":
        p.setBrush(duo_fill)
        p.drawEllipse(QPointF(12.0, 12.0), 9.2, 9.2)
        bars = [(7.0, 10.0, 4.0), (10.3, 6.5, 11.0), (13.6, 8.2, 7.6), (16.9, 10.5, 3.0)]
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        for bx, by, bh in bars:
            p.drawRoundedRect(QRectF(bx - 1.1, by, 2.2, bh), 1.1, 1.1)

    elif name == "m3u8":
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(12.0, 12.0), 2.5, 2.5)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawArc(QRectF(6.8, 6.8, 10.4, 10.4), 35 * 16, 110 * 16)
        p.drawArc(QRectF(6.8, 6.8, 10.4, 10.4), 215 * 16, 110 * 16)
        p.setPen(QPen(duo_mid, stroke_width, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(3.2, 3.2, 17.6, 17.6), 35 * 16, 110 * 16)
        p.drawArc(QRectF(3.2, 3.2, 17.6, 17.6), 215 * 16, 110 * 16)

    elif name == "translate":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(2.8, 3.5, 11.0, 10.5), 2.8, 2.8)
        p.setBrush(duo_mid)
        p.drawRoundedRect(QRectF(10.2, 10.0, 11.0, 10.5), 2.8, 2.8)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawLine(QPointF(5.5, 7.2), QPointF(11.0, 7.2))
        p.drawLine(QPointF(8.2, 5.2), QPointF(8.2, 11.2))
        p.drawPolyline(QPolygonF([QPointF(13.2, 18.2), QPointF(15.7, 12.5), QPointF(18.2, 18.2)]))
        p.drawLine(QPointF(14.0, 16.5), QPointF(17.4, 16.5))

    elif name == "trash":
        p.setBrush(duo_fill)
        p.drawRoundedRect(QRectF(6.5, 7.0, 11.0, 13.0), 2.4, 2.4)
        p.drawLine(QPointF(4.5, 7.0), QPointF(19.5, 7.0))
        p.drawLine(QPointF(9.5, 4.5), QPointF(14.5, 4.5))
        p.drawLine(QPointF(10.2, 10.5), QPointF(10.2, 16.5))
        p.drawLine(QPointF(13.8, 10.5), QPointF(13.8, 16.5))

    elif name == "refresh" or name == "history":
        p.setBrush(duo_fill)
        p.drawEllipse(QPointF(12.0, 12.0), 8.2, 8.2)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(5.0, 5.0, 14.0, 14.0), 35 * 16, 290 * 16)
        p.drawPolyline(QPolygonF([QPointF(15.0, 4.5), QPointF(19.2, 6.2), QPointF(16.5, 10.0)]))

    elif name == "moon":
        path = QPainterPath()
        path.addEllipse(QRectF(4.8, 4.8, 14.4, 14.4))
        cut = QPainterPath()
        cut.addEllipse(QRectF(9.5, 3.2, 12.2, 12.2))
        crescent = path.subtracted(cut)
        p.setBrush(duo_mid)
        p.drawPath(crescent)

    elif name == "sun":
        p.setBrush(duo_mid)
        p.drawEllipse(QPointF(12.0, 12.0), 4.5, 4.5)
        for i in range(8):
            ang = i * (math.pi / 4.0)
            x1, y1 = 12.0 + math.cos(ang) * 6.8, 12.0 + math.sin(ang) * 6.8
            x2, y2 = 12.0 + math.cos(ang) * 9.3, 12.0 + math.sin(ang) * 9.3
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    elif name == "bell":
        p.setBrush(duo_fill)
        p.drawArc(QRectF(6.0, 5.0, 12.0, 12.0), 0, 180 * 16)
        p.drawLine(QPointF(6.0, 11.0), QPointF(4.8, 16.2))
        p.drawLine(QPointF(18.0, 11.0), QPointF(19.2, 16.2))
        p.drawLine(QPointF(4.8, 16.2), QPointF(19.2, 16.2))
        p.drawArc(QRectF(10.0, 16.2, 4.0, 3.8), 180 * 16, 180 * 16)

    elif name == "chevron_down":
        p.drawPolyline(QPolygonF([QPointF(7.0, 9.5), QPointF(12.0, 14.5), QPointF(17.0, 9.5)]))

    elif name == "globe":
        p.setBrush(duo_fill)
        p.drawEllipse(QPointF(12.0, 12.0), 8.6, 8.6)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(3.6, 12.0), QPointF(20.4, 12.0))
        p.drawEllipse(QPointF(12.0, 12.0), 4.2, 8.6)

    p.restore()


def icon_pixmap(name: str, size: int = 20, color: Optional[QColor] = None, dpr: float = 2.0) -> QPixmap:
    pix = QPixmap(int(size * dpr), int(size * dpr))
    pix.fill(Qt.transparent)
    pix.setDevicePixelRatio(dpr)
    p = QPainter(pix)
    draw_icon(p, name, QRectF(0, 0, size, size), color=color)
    p.end()
    return pix


def make_qicon(name: str, size: int = 20, color: Optional[QColor] = None) -> QIcon:
    return QIcon(icon_pixmap(name, size=size, color=color))
