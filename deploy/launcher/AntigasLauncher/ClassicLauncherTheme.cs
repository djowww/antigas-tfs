using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace AntigasLauncher;

// Native interpretation of the site's classic-assets stone, parchment and ribbon.
// The material colors and square bevels are shared with classic-2004.css.
internal static class ClassicLauncherTheme
{
    internal static readonly Color Stone = Color.FromArgb(68, 70, 63);
    internal static readonly Color Paper = Color.FromArgb(255, 240, 210);
    internal static readonly Color Ink = Color.FromArgb(74, 43, 19);
    internal static readonly Color MutedInk = Color.FromArgb(103, 79, 49);
    internal static readonly Color Gold = Color.FromArgb(216, 193, 107);
    private static readonly Bitmap StoneTexture = MakeTexture(Stone, 64, 12, 74);
    private static readonly Bitmap PaperTexture = MakeTexture(Paper, 96, 7, 2004);

    internal static void Build(Form form, string subtitle, Label status, Label detail,
        ClassicProgressBar progress, Button primary, Button? secondary, Button close)
    {
        form.FormBorderStyle = FormBorderStyle.None;
        form.AutoScaleDimensions = new SizeF(96F, 96F);
        form.AutoScaleMode = AutoScaleMode.Dpi;
        form.ClientSize = new Size(596, 334);
        form.BackColor = Stone;
        form.ForeColor = Ink;
        form.Font = new Font("Verdana", 9F);

        var frame = new ClassicSurface(false) { Dock = DockStyle.Fill, Padding = new Padding(12) };
        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill, BackColor = Color.Transparent,
            ColumnCount = 1, RowCount = 3, Margin = Padding.Empty
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 102));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 58));
        frame.Controls.Add(layout);
        form.Controls.Add(frame);

        layout.Controls.Add(new ClassicBanner(subtitle)
        {
            Dock = DockStyle.Fill, Margin = new Padding(0, 0, 0, 10)
        }, 0, 0);

        var parchment = new ClassicSurface(true)
        {
            Dock = DockStyle.Fill, Padding = new Padding(18, 15, 18, 15),
            Margin = Padding.Empty
        };
        var information = new TableLayoutPanel
        {
            Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3,
            BackColor = Color.Transparent, Margin = Padding.Empty
        };
        information.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        information.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        information.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        information.RowStyles.Add(new RowStyle(SizeType.Absolute, 18));
        status.Dock = DockStyle.Fill;
        status.AutoSize = true;
        status.MinimumSize = new Size(0, 30);
        status.BackColor = Color.Transparent;
        status.ForeColor = Ink;
        status.Font = new Font("Verdana", 9.25F, FontStyle.Bold);
        status.Margin = Padding.Empty;
        status.TextAlign = ContentAlignment.MiddleLeft;
        detail.Dock = DockStyle.Fill;
        detail.BackColor = Color.Transparent;
        detail.ForeColor = MutedInk;
        detail.Margin = new Padding(0, 4, 0, 6);
        detail.TextAlign = ContentAlignment.TopLeft;
        progress.Dock = DockStyle.Fill;
        progress.Margin = Padding.Empty;
        progress.AccessibleName = "Progresso da atualização";
        information.Controls.Add(status, 0, 0);
        information.Controls.Add(detail, 0, 1);
        information.Controls.Add(progress, 0, 2);
        parchment.Controls.Add(information);
        layout.Controls.Add(parchment, 0, 1);

        var actions = new TableLayoutPanel
        {
            Dock = DockStyle.Fill, ColumnCount = 3, RowCount = 1,
            BackColor = Color.Transparent, Margin = new Padding(0, 12, 0, 0)
        };
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 42));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 36));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 22));
        actions.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        ConfigureButton(primary, 0, new Padding(0, 0, 8, 0));
        actions.Controls.Add(primary, 0, 0);
        if (secondary is not null)
        {
            ConfigureButton(secondary, 1, new Padding(0, 0, 8, 0));
            actions.Controls.Add(secondary, 1, 0);
        }
        ConfigureButton(close, 2, Padding.Empty);
        actions.Controls.Add(close, 2, 0);
        layout.Controls.Add(actions, 0, 2);
        form.AcceptButton = primary;
        form.CancelButton = close;
    }

    private static void ConfigureButton(Button button, int tabIndex, Padding margin)
    {
        button.Dock = DockStyle.Fill;
        button.Margin = margin;
        button.TabIndex = tabIndex;
        button.Font = new Font("Verdana", 9F, FontStyle.Bold);
        button.Cursor = Cursors.Hand;
        button.UseVisualStyleBackColor = false;
    }

    internal static void PaintMaterial(Graphics graphics, Rectangle bounds, bool parchment)
    {
        using var texture = new TextureBrush(parchment ? PaperTexture : StoneTexture);
        graphics.FillRectangle(texture, bounds);
    }

    internal static void Bevel(Graphics graphics, Rectangle bounds, Color light, Color dark, int depth = 2)
    {
        if (bounds.Width <= depth * 2 || bounds.Height <= depth * 2) return;
        using var top = new Pen(light);
        using var bottom = new Pen(dark);
        for (var i = 0; i < depth; i++)
        {
            var left = bounds.Left + i;
            var right = bounds.Right - i - 1;
            var upper = bounds.Top + i;
            var lower = bounds.Bottom - i - 1;
            graphics.DrawLine(top, left, upper, right, upper);
            graphics.DrawLine(top, left, upper, left, lower);
            graphics.DrawLine(bottom, left, lower, right, lower);
            graphics.DrawLine(bottom, right, upper, right, lower);
        }
    }

    private static Bitmap MakeTexture(Color color, int size, int variation, int seed)
    {
        var image = new Bitmap(size, size);
        var random = new Random(seed);
        for (var y = 0; y < size; y++)
        for (var x = 0; x < size; x++)
        {
            var shade = random.Next(-variation, variation + 1);
            image.SetPixel(x, y, Color.FromArgb(Math.Clamp(color.R + shade, 0, 255),
                Math.Clamp(color.G + shade, 0, 255), Math.Clamp(color.B + shade, 0, 255)));
        }
        return image;
    }
}

internal sealed class ClassicSurface : Panel
{
    private readonly bool _parchment;

    internal ClassicSurface(bool parchment)
    {
        _parchment = parchment;
        BackColor = parchment ? ClassicLauncherTheme.Paper : ClassicLauncherTheme.Stone;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
            ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
    }

    protected override void OnPaintBackground(PaintEventArgs e) =>
        ClassicLauncherTheme.PaintMaterial(e.Graphics, ClientRectangle, _parchment);

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var depth = Math.Max(2, DeviceDpi / 48);
        ClassicLauncherTheme.Bevel(e.Graphics, ClientRectangle,
            _parchment ? Color.FromArgb(235, 213, 169) : Color.FromArgb(133, 137, 116),
            _parchment ? Color.FromArgb(133, 97, 59) : Color.FromArgb(27, 30, 25), depth);
        if (_parchment)
        {
            var inner = Rectangle.Inflate(ClientRectangle, -depth, -depth);
            ClassicLauncherTheme.Bevel(e.Graphics, inner, Color.FromArgb(158, 126, 80),
                Color.FromArgb(255, 249, 229), 1);
        }
    }
}

internal sealed class ClassicBanner : Control
{
    private readonly string _subtitle;
    private bool _dragging;
    private Point _dragMouseOrigin, _dragWindowOrigin;

    internal ClassicBanner(string subtitle)
    {
        _subtitle = subtitle;
        TabStop = false;
        Cursor = Cursors.SizeAll;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
            ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
        AccessibleName = "Antigas 7.4, " + subtitle;
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button != MouseButtons.Left || FindForm() is not { WindowState: FormWindowState.Normal } form) return;
        _dragMouseOrigin = MousePosition;
        _dragWindowOrigin = form.Location;
        _dragging = true;
        Capture = true;
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (!_dragging || FindForm() is not { } form) return;
        var pointer = MousePosition;
        form.Location = new Point(_dragWindowOrigin.X + pointer.X - _dragMouseOrigin.X,
            _dragWindowOrigin.Y + pointer.Y - _dragMouseOrigin.Y);
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (e.Button != MouseButtons.Left) return;
        _dragging = false;
        Capture = false;
    }

    protected override void OnMouseCaptureChanged(EventArgs e)
    {
        base.OnMouseCaptureChanged(e);
        if (!Capture) _dragging = false;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        var scale = DeviceDpi / 96F;
        var bandHeight = (int)(25 * scale);
        var sky = new Rectangle(0, 0, Width, Height - bandHeight);
        using (var backdrop = new LinearGradientBrush(sky, Color.FromArgb(50, 52, 60),
            Color.FromArgb(17, 23, 41), LinearGradientMode.Horizontal))
            g.FillRectangle(backdrop, sky);
        using (var star = new SolidBrush(Color.FromArgb(121, 129, 147)))
        {
            // Quiet stars echo the site's existing sky.svg, without animation.
            int[] x = [8, 45, 77, 116, 130, 23, 61];
            int[] y = [13, 66, 32, 58, 7, 40, 4];
            for (var offset = 0; offset < Width; offset += (int)(139 * scale))
            for (var i = 0; i < x.Length; i++)
                g.FillRectangle(star, offset + x[i] * scale, y[i] * scale * .7F, scale, scale);
        }
        using var title = new Font("Georgia", 30F, FontStyle.Bold | FontStyle.Italic);
        var textBounds = new Rectangle((int)(18 * scale), (int)(5 * scale),
            Width - (int)(36 * scale), sky.Height - (int)(7 * scale));
        var shadowBounds = textBounds;
        shadowBounds.Offset((int)(2 * scale), (int)(2 * scale));
        TextRenderer.DrawText(g, "Antigas 7.4", title, shadowBounds,
            Color.FromArgb(8, 10, 15), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
        TextRenderer.DrawText(g, "Antigas 7.4", title, textBounds, Color.FromArgb(231, 197, 70),
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
        var ribbon = new Rectangle(0, sky.Bottom, Width, bandHeight);
        using (var wine = new SolidBrush(Color.FromArgb(98, 2, 0))) g.FillRectangle(wine, ribbon);
        ClassicLauncherTheme.Bevel(g, ribbon, Color.FromArgb(159, 93, 53), Color.FromArgb(49, 25, 16));
        using var caption = new Font("Verdana", 8.5F, FontStyle.Bold);
        TextRenderer.DrawText(g, _subtitle, caption, ribbon, Color.FromArgb(255, 244, 220),
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
        ClassicLauncherTheme.Bevel(g, ClientRectangle, Color.FromArgb(133, 137, 116), Color.FromArgb(23, 26, 22));
    }
}

internal sealed class ClassicButton : Button
{
    private readonly bool _primary;
    private bool _hovered, _pressed;

    internal ClassicButton(bool primary = false)
    {
        _primary = primary;
        FlatStyle = FlatStyle.Flat;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
            ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var top = _primary ? Color.FromArgb(113, 82, 36) : Color.FromArgb(76, 81, 69);
        var bottom = _primary ? Color.FromArgb(63, 43, 20) : Color.FromArgb(40, 45, 37);
        if (_hovered && Enabled) { top = ControlPaint.Light(top, .12F); bottom = ControlPaint.Light(bottom, .1F); }
        if (_pressed && Enabled) (top, bottom) = (bottom, top);
        if (!Enabled) { top = Color.FromArgb(61, 64, 55); bottom = Color.FromArgb(43, 47, 39); }
        using (var fill = new LinearGradientBrush(ClientRectangle, top, bottom, LinearGradientMode.Vertical))
            e.Graphics.FillRectangle(fill, ClientRectangle);
        var light = _primary && Enabled ? Color.FromArgb(199, 167, 93) : Color.FromArgb(140, 145, 120);
        var dark = Color.FromArgb(24, 27, 20);
        ClassicLauncherTheme.Bevel(e.Graphics, ClientRectangle, _pressed ? dark : light, _pressed ? light : dark,
            Math.Max(2, DeviceDpi / 48));
        var text = Rectangle.Inflate(ClientRectangle, -4, -4);
        if (_pressed) text.Offset(1, 1);
        TextRenderer.DrawText(e.Graphics, Text, Font, text,
            Enabled ? Color.FromArgb(255, 241, 205) : Color.FromArgb(172, 174, 156),
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
        if (Focused && ShowFocusCues && Enabled)
            ControlPaint.DrawFocusRectangle(e.Graphics, Rectangle.Inflate(ClientRectangle, -6, -6),
                Color.FromArgb(255, 241, 205), bottom);
    }

    protected override void OnMouseEnter(EventArgs e) { base.OnMouseEnter(e); _hovered = true; Invalidate(); }
    protected override void OnMouseLeave(EventArgs e) { base.OnMouseLeave(e); _hovered = false; _pressed = false; Invalidate(); }
    protected override void OnMouseDown(MouseEventArgs e) { base.OnMouseDown(e); if (e.Button == MouseButtons.Left) _pressed = true; Invalidate(); }
    protected override void OnMouseUp(MouseEventArgs e) { base.OnMouseUp(e); _pressed = false; Invalidate(); }
    protected override void OnKeyDown(KeyEventArgs e) { base.OnKeyDown(e); if (e.KeyCode == Keys.Space) _pressed = true; Invalidate(); }
    protected override void OnKeyUp(KeyEventArgs e) { base.OnKeyUp(e); _pressed = false; Invalidate(); }
    protected override void OnGotFocus(EventArgs e) { base.OnGotFocus(e); Invalidate(); }
    protected override void OnLostFocus(EventArgs e) { base.OnLostFocus(e); _pressed = false; Invalidate(); }
    protected override void OnEnabledChanged(EventArgs e) { base.OnEnabledChanged(e); Invalidate(); }
    protected override void OnTextChanged(EventArgs e) { base.OnTextChanged(e); Invalidate(); }
}

internal sealed class ClassicProgressBar : Control
{
    private readonly System.Windows.Forms.Timer _animation = new();
    private int _value, _maximum = 100, _phase;
    private ProgressBarStyle _style;

    internal ClassicProgressBar()
    {
        TabStop = false;
        AccessibleRole = AccessibleRole.ProgressBar;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
            ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
        _animation.Interval = 50;
        _animation.Tick += (_, _) => { _phase = (_phase + 3) % 1000; Invalidate(); };
    }

    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public int Maximum { get => _maximum; set { _maximum = Math.Max(1, value); _value = Math.Min(_value, _maximum); Invalidate(); } }
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public int Value
    {
        get => _value;
        set
        {
            _value = Math.Clamp(value, 0, _maximum);
            Invalidate();
            if (IsHandleCreated) AccessibilityNotifyClients(AccessibleEvents.ValueChange, -1);
        }
    }
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public ProgressBarStyle Style { get => _style; set { _style = value; UpdateAnimation(); Invalidate(); } }
    [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
    public int MarqueeAnimationSpeed { get => _animation.Interval; set { _animation.Interval = Math.Max(15, value); UpdateAnimation(); } }

    protected override void OnVisibleChanged(EventArgs e) { base.OnVisibleChanged(e); UpdateAnimation(); }
    private void UpdateAnimation()
    {
        if (IsDisposed || Disposing) return;
        _animation.Enabled = Visible && _style == ProgressBarStyle.Marquee && !DesignMode;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        using (var track = new SolidBrush(Color.FromArgb(67, 56, 39))) e.Graphics.FillRectangle(track, ClientRectangle);
        ClassicLauncherTheme.Bevel(e.Graphics, ClientRectangle, Color.FromArgb(111, 86, 52), Color.FromArgb(244, 221, 176));
        var inner = Rectangle.Inflate(ClientRectangle, -3, -3);
        if (inner.Width <= 0 || inner.Height <= 0) return;
        var fill = inner;
        if (_style == ProgressBarStyle.Marquee)
        {
            fill.Width = Math.Max(12, inner.Width / 5);
            fill.X = inner.Left - fill.Width + _phase * (inner.Width + fill.Width) / 1000;
            fill = Rectangle.Intersect(fill, inner);
        }
        else fill.Width = (int)((long)inner.Width * _value / _maximum);
        if (fill.Width > 0)
        {
            using var gold = new LinearGradientBrush(inner, Color.FromArgb(231, 204, 110),
                Color.FromArgb(146, 112, 45), LinearGradientMode.Vertical);
            e.Graphics.FillRectangle(gold, fill);
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) _animation.Dispose();
        base.Dispose(disposing);
    }

    protected override AccessibleObject CreateAccessibilityInstance() => new ProgressAccessibility(this);

    private sealed class ProgressAccessibility(ClassicProgressBar owner) : ControlAccessibleObject(owner)
    {
        public override AccessibleRole Role => AccessibleRole.ProgressBar;
        public override string? Value
        {
            get => owner.Style == ProgressBarStyle.Marquee ? "Em andamento" : $"{owner.Value * 100L / owner.Maximum}%";
            set { }
        }
    }
}
