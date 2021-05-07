from kivy import metrics

def snap_to_grid(grid_div, length=1, grid=1, roundup=False):
    grid /= grid_div
    if roundup:
        trunclength = (length // grid) * grid
        length = grid + trunclength if length - trunclength > 0 else trunclength
    else:
        length = (length // grid) * grid
    return length

def length_to_pixels(app, length, snap=False, grid=1, roundup=False):
    if snap:
        length = snap_to_grid(app.grid_div, length, grid, roundup)
    return metrics.dp(length * (60.0 * app.zoom))

def pixels_to_length(app, pixels, snap=False, grid=1, roundup=False):
    length = pixels / (metrics.dp(60.0) * app.zoom)
    if snap:
        length = snap_to_grid(app.grid_div, length, grid, roundup)
    return length


