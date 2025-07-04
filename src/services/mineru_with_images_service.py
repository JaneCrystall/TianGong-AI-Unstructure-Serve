import os
import tempfile
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod

from src.models.models import ResponseWithPageNum, TextElementWithPageNum
# from src.services.vision_service_openai import vision_completion_openai
from src.services.vision_service_genimi import vision_completion_genimi


def image_text(item):
    captions = item.get("img_caption") or []
    footnotes = item.get("img_footnote") or []
    return "\n".join([*captions, *footnotes])


def table_text(item):
    return "\n".join(
        filter(
            None,
            [
                "\n".join(item.get("table_caption", [])),
                item.get("table_body", ""),
                "\n".join(item.get("table_footnote", [])),
            ],
        )
    )


def mineru_service(file_path):
    # read bytes
    reader = FileBasedDataReader("")
    pdf_bytes = reader.read(file_path)

    # dataset
    ds = PymuDocDataset(pdf_bytes)

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_writer = FileBasedDataWriter(tmp_dir)
        if ds.classify() == SupportedPdfParseMethod.OCR:
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
        else:
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)

        # 获取内容列表
        content_list_content = pipe_result.get_content_list(tmp_dir)

        # 处理内容并添加上下文
        result_items = []
        total_images = sum(
            1 for item in content_list_content if item["type"] == "image" and "img_path" in item
        )
        image_count = 0

        print(f"Processing document: Found {total_images} images to analyze")

        for i, item in enumerate(content_list_content):
            if item["type"] == "image" and "img_path" in item:

                image_count += 1
                print(
                    f"Processing image {image_count}/{total_images} on page {item['page_idx'] + 1}..."
                )

                # 获取上下文（前后两个文本元素）
                context_before = ""
                context_after = ""

                # 查找前面的文本
                j = i - 1
                count = 0
                while j >= 0 and count < 2:
                    if (
                        content_list_content[j]["type"] == "text"
                        and content_list_content[j].get("text", "").strip()
                    ):
                        context_before = content_list_content[j]["text"] + "\n" + context_before
                        count += 1
                    j -= 1

                # 查找后面的文本
                j = i + 1
                count = 0
                while j < len(content_list_content) and count < 2:
                    if (
                        content_list_content[j]["type"] == "text"
                        and content_list_content[j].get("text", "").strip()
                    ):
                        context_after += content_list_content[j]["text"] + "\n"
                        count += 1
                    j += 1

                # 提取图像信息
                img_path = os.path.join(tmp_dir, item["img_path"])
                captions = "\n".join(item.get("img_caption") or [])
                footnotes = "\n".join(item.get("img_footnote") or [])

                # 调用vision服务
                prompt_parts = []
                if captions.strip():
                    prompt_parts.append(f"Image caption: {captions}")
                if footnotes.strip():
                    prompt_parts.append(f"Image footnote: {footnotes}")
                if context_before.strip():
                    prompt_parts.append(f"Context before: {context_before}")
                if context_after.strip():
                    prompt_parts.append(f"Context after: {context_after}")

                print(f"Calling vision completion for image {image_count}/{total_images}...")
                # vision_result = vision_completion_openai(
                #     img_path,
                #     "\n".join(prompt_parts),
                # )
                vision_result = vision_completion_genimi(
                    img_path,
                    "\n".join(prompt_parts),
                )
                print(f"✓ Vision analysis complete for image {image_count}/{total_images}")

                # 将结果添加到响应中
                result_items.append(
                    TextElementWithPageNum(
                        text=f"{image_text(item)}\nImage Description: {vision_result}",
                        page_number=item["page_idx"] + 1,
                    )
                )
            elif (
                (item["type"] in ("text", "equation") and item.get("text", "").strip())
                or (
                    item["type"] == "image"
                    and (item.get("img_caption") or item.get("img_footnote"))
                )
                or (
                    item["type"] == "table"
                    and (
                        item.get("table_caption")
                        or item.get("table_body")
                        or item.get("table_footnote")
                    )
                )
            ):
                # 处理其他类型的元素（与原代码相同）
                result_items.append(
                    TextElementWithPageNum(
                        text=(
                            item["text"]
                            if item["type"] in ("text", "equation")
                            else table_text(item) if item["type"] == "table" else image_text(item)
                        ),
                        page_number=item["page_idx"] + 1,
                    )
                )
        print(f"Completed processing all {total_images} images")
        response = ResponseWithPageNum(result=result_items)
        return response
