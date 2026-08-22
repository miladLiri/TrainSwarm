package transfer

import "context"

const ProtocolID = "/p2p-file-transfer/1.0.0"

func SendFile(ctx context.Context) error {
	return nil
}

func ReceiveFile(ctx context.Context) error {
	return nil
}

func CancelTransfer(transferID string) error {
	return nil
}
