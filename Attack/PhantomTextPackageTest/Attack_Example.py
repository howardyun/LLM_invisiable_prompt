### Before You Run this Script , please install package  phantomtext
### pip install phantomtext


#  Code Injection Example
from phantomtext.injection.zerosize_injection import ZeroSizeInjection
from phantomtext.injection.camouflage_injection import CamouflageInjection
from phantomtext.injection.transparent_injection import TransparentInjection

# Zero-size injection
injector = ZeroSizeInjection(modality="default", file_format="pdf")

injector2 = TransparentInjection(modality="default", file_format="pdf")

injector.apply(input_document="DGA_IWQOS2025.pdf",
               injection="Hidden content",
               output_path="injected_document.pdf")
injector2.apply(input_document="DGA_IWQOS2025.pdf", injection = "Hidden content", output_path="injected_document_Trans.pdf")

# # Transparent injection
# injector = TransparentInjection(modality="opacity-0", file_format="html")
# injector.apply(input_document="document.html",
#                injection="Invisible text",
#                output_path="injected_document.html")