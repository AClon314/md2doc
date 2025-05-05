--[[
    This filter adds a custom style "inline code" to all inline code elements.
]]

function Code(el)
    -- Wrap the inline code element in a Div with the custom style
    return pandoc.Span(el.text, {['custom-style'] = "inline code"})
end
