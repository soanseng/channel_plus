defmodule ChannelPlus.CLI do
  @moduledoc """
  Documentation for Scraping.
  """
  def main(args \\ []) do
    args
    |> parse_args
    |> start
  end

  def parse_args(args) do
    {opts, _, _} =
      args
      |> OptionParser.parse(
        strict: [path: :string, link: :string, start: :string, final: :string]
      )
      opts
  end

  def start([path: path, link: link, start: start_ep, final: final_ep]) do
    get_all_links(link, String.to_integer(start_ep), String.to_integer(final_ep))
    |> Enum.each(&download(&1, path))
  end

  def retrive_link(link, number) do
    response = HTTPotion.get(link <> "?page=" <> Integer.to_string(number))
    rule = ~r/window.__PRELOADED_STATE__ = (?<json>{.+)/
    data = Regex.named_captures(rule, response.body)
    result = Jason.decode!(data["json"])

    audio_data =
      result["reducers"]["languageEpisode"]["data"]
      |> Enum.map(fn item ->
        %{
          name: item["audio"]["name"],
          location: "https://channelplus.ner.gov.tw/api/audio/" <> item["audio"]["key"]
        }
      end)
  end

  def get_all_links(link, start_ep, final_ep) do
    start_page =
      if rem(start_ep, 10) != 0 do
        Kernel.div(start_ep, 10) + 1
      else
        Kernel.div(start_ep, 10)
      end

    final_page =
      if rem(final_ep, 10) != 0 do
        Kernel.div(final_ep, 10) + 1
      else
        Kernel.div(final_ep, 10)
      end

    IO.puts "start collects all links"

    Enum.map(start_page..final_page, fn page -> retrive_link(link, page) end)
    |> List.flatten()
  end

  def download(audio, path) do
    timeout = 3000_000
    opts = [timeout: timeout]
    %HTTPotion.Response{body: body} = HTTPotion.get!(audio.location, opts)
    File.write!(path <> audio.name, body)
    IO.puts("Downloaded #{audio.name} !")
  end
end

