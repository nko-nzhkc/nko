from pathlib import Path


def test_mock():
    """Тест для проверки работы воркфлоу."""
    workflow_path = Path('.github/workflows/pr_test.yml')
    expected_dir = Path('.github/workflows')
    assert workflow_path.is_file(), 'Файл pr_test.yml не существует'
    assert workflow_path.parent.resolve() == expected_dir.resolve(), (
        'Файл pr_test.yml не найден в папке .github'
    )
