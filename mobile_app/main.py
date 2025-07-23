import flet as ft
from utils import api_client, local_storage
import threading

# --- অ্যাপের থিম এবং রঙ ---
THEME = {
    "background": "#0d1b2a",
    "card_background": "#1B263B",
    "text": "#FFFFFF",
    "light_text": "#EAEAEA",
    "accent_start": "#E040FB",
    "accent_end": "#7B1FA2",
}

# --- মূল অ্যাপ ---
def main(page: ft.Page):
    page.title = "শ্রুতিপাঠ"
    page.bgcolor = THEME["background"]
    page.padding = 0
    page.fonts = {
        "Kalpurush": "https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-Regular.ttf"
    }
    page.theme = ft.Theme(font_family="Kalpurush")
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # --- অডিও প্লেয়ার ও ভিউ ম্যানেজমেন্ট ---
    audio_player = ft.Audio(autoplay=False, volume=1)
    page.overlay.append(audio_player)

    def play_audio(url, is_local=False):
        print(f"Playing {'local' if is_local else 'remote'} audio: {url}")
        audio_player.src = url
        page.update()
        audio_player.play()

    main_view_stack = ft.AnimatedSwitcher(
        content=ft.Column(
            [ft.ProgressRing(), ft.Text("লোড হচ্ছে...", color=THEME["text"])],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=300,
        reverse_duration=300,
        expand=True,
    )

    # --- স্ক্রিন ভিউ ---
    def build_home_view(subjects, config):
        scrolling_notice_text = config.get("scrollingNotice", {}).get("text", "শ্রুতিপাঠ অ্যাপে আপনাকে স্বাগতম!")
        
        def create_subject_card(subject):
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Icon(ft.icons.BOOK_OUTLINED, color=THEME["text"], size=48),
                            width=140, height=100, bgcolor=THEME["background"],
                            border_radius=10, alignment=ft.alignment.center
                        ),
                        ft.Text(subject.get("subjectName"), color=THEME["text"], weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10
                ),
                width=160, padding=10, bgcolor=THEME["card_background"],
                border_radius=15, ink=True, on_click=lambda e, s=subject: open_subject_view(s)
            )

        grid = ft.GridView(
            expand=False, runs_count=5, max_extent=180, child_aspect_ratio=0.9,
            spacing=15, run_spacing=15,
        )

        if subjects:
            for subject in subjects:
                grid.controls.append(create_subject_card(subject))
        else:
            grid.controls.append(ft.Text("কোনো বিষয় পাওয়া যায়নি।", color=THEME["light_text"]))
        
        return ft.Column(
            controls=[
                ft.Container(
                    # MarqueeText এর একটি সিম্পল সংস্করণ
                    content=ft.Row([ft.Text(scrolling_notice_text, size=14, color=THEME["light_text"])]),
                    padding=ft.padding.symmetric(vertical=8, horizontal=12),
                    bgcolor=THEME["card_background"]
                ),
                ft.ListView(
                    [
                        ft.Text("বিষয়সমূহ", size=24, weight=ft.FontWeight.BOLD, color=THEME["text"]),
                        grid
                    ],
                    expand=True, spacing=20, padding=20
                )
            ],
            expand=True
        )

    def build_subject_view(subject):
        def download_audio_file(button_control, url, on_complete_callback):
            button_control.icon = ft.icons.HOURGLASS_TOP
            button_control.disabled = True
            page.update()

            def download_complete(local_path):
                if local_path:
                    on_complete_callback() # UI আপডেট করার জন্য কলব্যাক
                else:
                    button_control.icon = ft.icons.ERROR
                    button_control.icon_color = "red"
                    button_control.disabled = False
                page.update()

            threading.Thread(target=lambda: download_complete(api_client.download_audio(url, lambda p: None))).start()

        def create_chapter_tile(chapter):
            option_controls = []
            audio_options_template = subject.get("audio_options_template", [])

            for option_template in audio_options_template:
                key = option_template.get("key")
                label = option_template.get("label", "Play")
                audio_url = chapter.get("options", {}).get(key)

                if audio_url:
                    is_file_downloaded = local_storage.is_downloaded(audio_url)
                    local_path = local_storage.get_local_url(audio_url)
                    
                    download_button = ft.IconButton(
                        icon=ft.icons.DOWNLOAD_DONE if is_file_downloaded else ft.icons.DOWNLOAD,
                        icon_color="green" if is_file_downloaded else THEME["accent_start"],
                        tooltip="ডাউনলোড করা আছে" if is_file_downloaded else "ডাউনলোড করুন",
                    )
                    
                    list_tile = ft.ListTile(
                        leading=ft.Icon(ft.icons.PLAY_CIRCLE_FILL, color=THEME["accent_start"]),
                        title=ft.Text(label, color=THEME["light_text"]),
                        trailing=download_button,
                    )
                    
                    def create_click_handler(is_downloaded, local_p, remote_url, button, tile):
                        def on_click(e):
                            if is_downloaded:
                                play_audio(local_p, is_local=True)
                            else:
                                play_audio(remote_url)
                        return on_click
                    
                    def create_download_handler(url, button, tile):
                        def on_download(e):
                            # ডাউনলোড শেষ হলে পুরো টাইলটি রি-রেন্ডার করার জন্য একটি কলব্যাক পাস করা হচ্ছে
                            def on_complete():
                                # অধ্যায়টি আবার নতুন করে তৈরি করে লিস্টে প্রতিস্থাপন করা
                                new_tile = create_chapter_tile(chapter)
                                # পুরনো টাইল খুঁজে বের করে প্রতিস্থাপন করতে হবে
                                try:
                                    index = expansion_tile.controls.index(tile.parent)
                                    expansion_tile.controls[index] = new_tile.controls[index]
                                    page.update()
                                except (ValueError, AttributeError):
                                    # যদি কোনো কারণে খুঁজে না পাওয়া যায়, পুরো ভিউ রিফ্রেশ করা যেতে পারে
                                    open_subject_view(subject)

                            download_audio_file(button, url, on_complete)
                        return on_download
                    
                    list_tile.on_click = create_click_handler(is_file_downloaded, local_path, audio_url, download_button, list_tile)
                    download_button.on_click = create_download_handler(audio_url, download_button, list_tile)

                    option_controls.append(list_tile)
            
            expansion_tile = ft.ExpansionTile(
                title=ft.Text(chapter.get("chapterName", "Unknown Chapter"), color=THEME["text"], weight=ft.FontWeight.W_500),
                leading=ft.Icon(ft.icons.MENU_BOOK, color=THEME["light_text"]),
                controls=option_controls,
                tile_padding=ft.padding.symmetric(horizontal=15)
            )
            return expansion_tile

        chapter_list = ft.ListView(expand=True, spacing=5)
        chapters = subject.get("chapters", [])
        if chapters:
            for chapter in chapters:
                chapter_list.controls.append(create_chapter_tile(chapter))
        else:
            chapter_list.controls.append(ft.Container(content=ft.Text("এই বিষয়ে এখনো কোনো অধ্যায় যোগ করা হয়নি।", color=THEME["light_text"]), padding=20))
        
        return ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.IconButton(icon=ft.icons.ARROW_BACK, on_click=lambda _: close_view(), icon_color=THEME["text"]),
                        ft.Text(subject.get("subjectName", "Subject"), size=20, weight=ft.FontWeight.BOLD, color=THEME["text"])
                    ]),
                    padding=ft.padding.only(top=10, left=10, right=10, bottom=5)
                ),
                chapter_list
            ], expand=True)

    # --- ভিউ নেভিগেশন ---
    def open_subject_view(subject_data):
        main_view_stack.content = build_subject_view(subject_data)
        page.update()

    def close_view():
        subjects, config = local_storage.load_data('subjects'), local_storage.load_data('config')
        if subjects is not None:
            main_view_stack.content = build_home_view(subjects, config or {})
        else:
            main_view_stack.content = build_loading_view("ক্যাশ থেকে লোড করা যায়নি।")
        page.update()

    def build_loading_view(text="লোড হচ্ছে..."):
        return ft.Column([ft.ProgressRing(), ft.Text(text, color=THEME["text"])], expand=True, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    
    # --- অ্যাপ চালু হওয়ার সময় ডেটা লোড ---
    def load_initial_data():
        subjects, config = api_client.get_app_data()
        if subjects is None: # ইন্টারনেট বা ডেটাবেস সংযোগ না থাকলে
            main_view_stack.content = ft.Column([
                ft.Icon(ft.icons.WIFI_OFF, color="red", size=48),
                ft.Text("ডেটা লোড করা যায়নি", color=THEME["text"], size=18),
                ft.Text("ইন্টারনেট সংযোগ চেক করে অ্যাপটি আবার চালু করুন।", color=THEME["light_text"], text_align=ft.TextAlign.CENTER)
            ], expand=True, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        else:
            main_view_stack.content = build_home_view(subjects, config or {})
        page.update()

    page.add(main_view_stack)
    
    threading.Thread(target=load_initial_data).start()

# --- অ্যাপটি শুরু করা ---
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")