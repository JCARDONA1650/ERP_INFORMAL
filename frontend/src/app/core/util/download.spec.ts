import { saveBlob } from './download';

describe('saveBlob', () => {
  it('crea un enlace temporal con el nombre de archivo y lo libera', () => {
    const create = vi.fn(() => 'blob:x');
    const revoke = vi.fn();
    URL.createObjectURL = create;
    URL.revokeObjectURL = revoke;
    let downloaded = '';
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      downloaded = this.download;
    });

    saveBlob(new Blob(['x']), 'nomina.xlsx');

    expect(downloaded).toBe('nomina.xlsx');
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalledWith('blob:x');
    expect(document.querySelector('a[download]')).toBeNull();
    click.mockRestore();
  });
});
