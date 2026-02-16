# Contributing

Contributions are welcome! Please open an issue or pull request.

## Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) coding style
- Add tests for new features or bug fixes
- Keep algorithm code in `VoronoiPattern/lib/` (no Fusion 360 API dependency)
- Keep tests in `tests/` (runnable with `pytest` outside Fusion 360)
- Use only Python standard library in `lib/` modules (no numpy, scipy, shapely, etc.)

## Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Open a pull request

## Reporting Issues

Please include:
- Fusion 360 version
- OS (Windows/macOS)
- Steps to reproduce
- Error messages or screenshots
