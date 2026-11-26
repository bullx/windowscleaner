using WindowsCleaner;

namespace WindowsCleaner.App;

public static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        if (args.Any(a => a == "--cli"))
            return Cli.Run(args);
        var app = new App();
        app.InitializeComponent();
        app.Run(new MainWindow());
        return 0;
    }
}
