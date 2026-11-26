using System.Globalization;
using System.Windows.Data;
using System.Windows.Media;

namespace WindowsCleaner.App;

public sealed class RiskBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var risk = value?.ToString()?.ToLowerInvariant();
        var color = risk switch
        {
            "safe" => Color.FromRgb(0x1E, 0x3A, 0x5F),
            "aggressive" => Color.FromRgb(0xDC, 0x26, 0x26),
            _ => Color.FromRgb(0x47, 0x55, 0x69),
        };
        return new SolidColorBrush(color);
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}

public sealed class StatusBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        var status = value?.ToString() ?? "";
        var color = status switch
        {
            "Failed" or "Not fixed" or "Failed — Needs Admin" => Color.FromRgb(0xDC, 0x26, 0x26),
            "Fixed" or "Needs Admin" or "Still open" or "Still present" => Color.FromRgb(0x1E, 0x3A, 0x5F),
            _ => Color.FromRgb(0x47, 0x55, 0x69),
        };
        return new SolidColorBrush(color);
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}
