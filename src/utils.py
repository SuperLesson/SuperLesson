import os


class LessonFiles:
    """Class to find all files for a given lesson id."""

    lesson_root: str

    def __init__(self, lesson: str):
        current_script_directory = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_script_directory, '..'))

        lesson_root = os.path.join(project_root, 'lessons', lesson)
        if os.path.exists(lesson_root):
            self.lesson_root = lesson_root
        elif os.path.exists(lesson):
            self.lesson_root = lesson
        else:
            raise ValueError(f"Lesson {lesson} not found")

        files = self._get_files()
        for file in files:
            if file.endswith(f"{lesson}.mp4"):
                self.transcription_source = file
            elif file.endswith(f"{lesson}.pdf"):
                self.lecture_notes = file

    def _get_files(self) -> list[str]:
        """All usable files in lesson folder."""
        print("Searching for files...")
        lesson_files: list[str] = []
        for root, _, files in os.walk(self.lesson_root):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    lesson_files.append(file_path)
                except ValueError:
                    pass

        return lesson_files
